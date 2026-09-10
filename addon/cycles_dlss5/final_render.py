"""Postprocess a completed render with a snapshot of the scene's NR settings.

The original Render Result and configured output file are never overwritten.
Only verified SDR output is published; render settings/compositor stay unchanged.
"""
import json
from pathlib import Path
import tempfile
import bpy
from bpy.app.handlers import persistent
import numpy as np
from .frame_job import FrameJob
from .render_payload import prepare_image, publish_image
from . import output
from .styles import values

_pending = None
_active = None
_last_image = None
_request = None


def show_result(context):
    """Show the full processed image in a separate Image Editor window."""
    if not has_result() or bpy.app.background:
        return False
    from . import result_viewer
    return result_viewer.show(context, _last_image)


def prefs():
    entry = bpy.context.preferences.addons.get(__package__)
    if entry is None:
        raise ValueError('Аддон не включён')
    return entry.preferences


def status(message):
    prefs().final_status = message
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            area.tag_redraw()


def has_result():
    try:
        return _last_image is not None and bpy.data.images.get(_last_image.name) == _last_image
    except ReferenceError:
        return False


def has_render():
    image = bpy.data.images.get('Render Result')
    return image is not None and image.has_data


def runtime_paths():
    p = prefs()
    from .runtime_setup import resolve
    return resolve(bpy.path.abspath(p.frame_runtime_directory) if p.frame_runtime_directory else '',
                   bpy.path.abspath(p.frame_host) if p.frame_host else '')


def create_job(payload, settings):
    p = prefs()
    if not p.experimental_native_session:
        host, runtime = runtime_paths()
        return FrameJob(payload, host, runtime, settings)
    from .native_frame_job import NativeFrameJob
    if not p.bridge_path or not p.runtime_directory:
        raise ValueError('Укажите Native Bridge DLL и NVIDIA NGX Runtime в настройках аддона')
    command = [bpy.app.binary_path, '--background', '--factory-startup', '--disable-autoexec',
               '--python-exit-code', '1', '--python']
    return NativeFrameJob(payload, command, bpy.path.abspath(p.bridge_path),
                          bpy.path.abspath(p.runtime_directory), settings)


def check_selected_runtime():
    p = prefs()
    if not p.experimental_native_session:
        runtime_paths()
        return
    from .native_frame_job import PINNED
    from .probe import digest
    if not p.bridge_path or not p.runtime_directory:
        raise ValueError('Укажите Native Bridge DLL и NVIDIA NGX Runtime в настройках аддона')
    for name, expected in PINNED.items():
        path = (Path(bpy.path.abspath(p.bridge_path)) if name == 'dlss5nr_bridge.dll'
                else Path(bpy.path.abspath(p.runtime_directory))/name)
        if not path.is_file() or digest(path) != expected:
            raise ValueError('Неверный экспериментальный runtime: ' + name)


def capture_render(scene, folder):
    if scene.display_settings.display_device != 'sRGB':
        raise ValueError('DLSS output поддерживает только sRGB SDR; HDR не преобразуется молча')
    image = bpy.data.images.get('Render Result')
    if image is None:
        raise ValueError('Сначала завершите рендер')
    settings = scene.render.image_settings
    keys = ('media_type', 'file_format', 'color_mode', 'color_depth')
    previous = {key: getattr(settings, key) for key in keys}
    snapshot = None
    try:
        settings.media_type = 'IMAGE'
        settings.file_format = 'PNG'
        settings.color_mode = 'RGBA'
        settings.color_depth = '8'
        filename = str(folder / 'original.png')
        image.save_render(filename, scene=scene)
        snapshot = bpy.data.images.load(filename, check_existing=False)
        snapshot.colorspace_settings.name = 'Non-Color'
        width, height = snapshot.size
        pixels = np.empty(width * height * 4, dtype=np.float32)
        snapshot.pixels.foreach_get(pixels)
        if not np.isfinite(pixels).all():
            raise ValueError('Render Result содержит недопустимые значения')
        rgba = np.rint(np.clip(pixels.reshape(height, width, 4)[::-1], 0, 1) * 255).astype(np.uint8)
        prepare_image(folder, rgba.tobytes(), width, height)
    finally:
        # Media type may constrain file_format; restore it before its dependent fields.
        for key in keys:
            setattr(settings, key, previous[key])
        if snapshot is not None:
            bpy.data.images.remove(snapshot)


def begin(scene, settings, output_settings=None):
    global _active
    if _active is not None:
        raise ValueError('Обработка DLSS уже выполняется')
    config = output_settings if output_settings is not None else output.snapshot(scene, 'VIEWPORT')
    from . import viewport
    viewport.stop(keep_target=True)
    folder = tempfile.TemporaryDirectory(prefix='dlss5-final-input-', ignore_cleanup_errors=True)
    job = None
    try:
        capture_render(scene, Path(folder.name))
        job = create_job(folder.name, settings)
        job.start()
        _active = {'job': job, 'settings': settings, 'scene': scene.name, 'frame': scene.frame_current,
                   'output': config}
        status('NR: 25% · этапы обработки')
        bpy.app.timers.register(poll_job, first_interval=.1)
    except Exception:
        _active = None
        if job is not None:
            job.close()
        raise
    finally:
        folder.cleanup()


def poll_job():
    global _active, _last_image
    if _active is None:
        return None
    job = _active['job']
    done = False
    try:
        code = job.poll()
        if code is None:
            percent = job.progress()
            if percent != _active.get('progress'):
                _active['progress'] = percent
                status(f'NR: {percent}% · этапы обработки')
            return .1
        done = True
        report = job.finish(code)
        report.update(settings=_active['settings'], scene=_active['scene'], frame=_active['frame'],
                      output=_active['output'])
        path = job.work / 'final.png'
        publish_image(job, report, path)
        image = bpy.data.images.load(str(path), check_existing=False)
        image.name = 'DLSS Render'
        image.colorspace_settings.name = 'sRGB'
        image.use_view_as_render = False
        image.pack()
        image['dlss5_report'] = json.dumps(report)
        _last_image = image
        status('NR: готово — 100%')
        # Save/display failures must not discard a verified, packed result.
        try:
            if report['output']['destination'] in {'BOTH', 'DISK'}:
                destination = output.save(image, report['output'])
                report['saved_path'] = str(destination)
                image['dlss5_report'] = json.dumps(report)
                status('100% · Сохранено: ' + str(destination))
            if report['output']['destination'] != 'DISK' and bpy.context.scene.name == report['scene']:
                show_result(bpy.context)
        except Exception as error:
            status(f'NR выполнен; ошибка вывода: {error}')
        return None
    except Exception as error:
        done = True
        status('Ошибка DLSS: ' + str(error))
        return None
    finally:
        if done:
            _active = None
            job.close()


def stop_final():
    global _pending, _active, _request
    _pending = None
    _request = None
    if bpy.app.timers.is_registered(start_pending):
        bpy.app.timers.unregister(start_pending)
    if bpy.app.timers.is_registered(poll_job):
        bpy.app.timers.unregister(poll_job)
    active, _active = _active, None
    if active is not None:
        active['job'].close()


@persistent
def render_init(scene, *_):
    global _pending, _request
    _pending = None
    if not scene.dlss5_style.final_enabled:
        return
    if _active is not None:
        status('Новый рендер без DLSS: предыдущая обработка ещё выполняется')
        return
    try:
        check_selected_runtime()
        from . import viewport
        viewport.stop(keep_target=True)
        config = _request if _request is not None else output.snapshot(scene, 'VIEWPORT')
        _request = None
        _pending = {'scene': scene, 'settings': values(scene.dlss5_style), 'frames': 0, 'output': config}
        status('Рендер: параметры DLSS зафиксированы')
    except Exception as error:
        status('DLSS не запущен: ' + str(error))


@persistent
def render_post(scene, *_):
    if _pending is not None and _pending['scene'] == scene:
        _pending['frames'] += 1


@persistent
def render_complete(scene, *_):
    if _pending is not None and _pending['scene'] == scene:
        if not bpy.app.timers.is_registered(start_pending):
            bpy.app.timers.register(start_pending, first_interval=.1)


@persistent
def render_cancel(scene, *_):
    global _pending
    if _pending is not None and _pending['scene'] == scene:
        _pending = None
        status('Рендер отменён; обработка DLSS не запускалась')


def start_pending():
    global _pending
    if _pending is None:
        return None
    if bpy.app.is_job_running('RENDER'):
        return .1
    pending, _pending = _pending, None
    try:
        if pending['frames'] != 1:
            raise ValueError('Обработка анимации не поддерживается; выберите один кадр')
        begin(pending['scene'], pending['settings'], pending['output'])
    except Exception as error:
        status('Ошибка DLSS: ' + str(error))
    return None


@persistent
def load_pre(*_):
    global _last_image, _request
    from . import viewport
    viewport.stop()
    from . import result_viewer
    result_viewer.forget()
    stop_final()
    _last_image = None
    _request = None


HANDLERS = ((bpy.app.handlers.render_init, render_init), (bpy.app.handlers.render_post, render_post),
            (bpy.app.handlers.render_complete, render_complete), (bpy.app.handlers.render_cancel, render_cancel),
            (bpy.app.handlers.load_pre, load_pre))


def register_handlers():
    from .viewport import scene_changed
    if scene_changed not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(scene_changed)
    for collection, callback in HANDLERS:
        if callback not in collection:
            collection.append(callback)


def unregister_handlers():
    from . import viewport
    viewport.stop()
    from . import result_viewer
    result_viewer.forget()
    if viewport.scene_changed in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(viewport.scene_changed)
    stop_final()
    for collection, callback in HANDLERS:
        if callback in collection:
            collection.remove(callback)


class CYCLES_DLSS5_OT_final_render(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.final_render'
    bl_label = 'Рендер с эффектом…'

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=460)

    def draw(self, context):
        output.draw(self.layout, context.scene)
        self.layout.label(text='Общие параметры NR из панели viewport.')
        self.layout.label(text='Камера, разрешение и семплы — из сцены Blender.')

    def execute(self, context):
        global _request
        try:
            if _active is not None or _pending is not None or bpy.app.is_job_running('RENDER'):
                raise ValueError('Дождитесь завершения текущего рендера / DLSS')
            check_selected_runtime()
            _request = output.snapshot(context.scene, 'DISK')
            context.scene.dlss5_style.final_enabled = True
            view = context.preferences.view
            display = view.render_display_type
            try:
                # File-only rendering must not open a Render Result window.
                # Never persist this preference.
                view.render_display_type = 'NONE'
                result = bpy.ops.render.render('INVOKE_DEFAULT')
            finally:
                view.render_display_type = display
            if result not in ({'FINISHED'}, {'RUNNING_MODAL'}):
                _request = None
            return {'FINISHED'} if result in ({'FINISHED'}, {'RUNNING_MODAL'}) else {'CANCELLED'}
        except Exception as error:
            _request = None
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class CYCLES_DLSS5_OT_final_stop(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.final_stop'
    bl_label = 'Остановить обработку DLSS'

    def execute(self, context):
        stop_final()
        status('DLSS отменён; рендер Blender продолжается' if bpy.app.is_job_running('RENDER') else
               'Обработка DLSS остановлена; исходный рендер не изменён')
        return {'FINISHED'}


class CYCLES_DLSS5_OT_final_apply(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.final_apply'
    bl_label = 'Применить к готовому рендеру'
    bl_description = 'Обработать исходный Render Result с текущими настройками, без повторного рендера'

    @classmethod
    def poll(cls, context):
        return (_active is None and _pending is None and not bpy.app.is_job_running('RENDER')
                and has_render())

    def execute(self, context):
        try:
            begin(context.scene, values(context.scene.dlss5_style))
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class CYCLES_DLSS5_OT_final_show(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.final_show'
    bl_label = 'Показать результат'

    @classmethod
    def poll(cls, context):
        return has_result() and context.area is not None and context.window is not None

    def execute(self, context):
        try:
            return {'FINISHED'} if show_result(context) else {'CANCELLED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class CYCLES_DLSS5_OT_final_save(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.final_save'
    bl_label = 'Сохранить результат…'
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='*', options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return has_result()

    def invoke(self, context, event):
        config = output.snapshot(context.scene)
        self.filepath = config['path']
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        try:
            config = output.snapshot(context.scene)
            path = Path(bpy.path.abspath(self.filepath))
            if context.scene.render.use_file_extension:
                path = path.with_suffix(context.scene.render.file_extension)
            path = output.save(_last_image, config, path)
            self.report({'INFO'}, 'Сохранено: ' + str(path))
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


CLASSES = (CYCLES_DLSS5_OT_final_render, CYCLES_DLSS5_OT_final_stop,
           CYCLES_DLSS5_OT_final_show, CYCLES_DLSS5_OT_final_save, CYCLES_DLSS5_OT_final_apply)


def draw_final(layout, context):
    box = layout.box()
    if _active is not None or _pending is not None:
        percent = _active.get('progress', 15) if _active is not None else 0
        box.progress(factor=percent / 100, type='BAR', text=f'NR: {percent}% · этапы')
        box.operator('cycles_dlss5.final_stop', icon='CANCEL')
    elif not bpy.app.is_job_running('RENDER'):
        box.operator_context = 'INVOKE_DEFAULT'
        box.operator('cycles_dlss5.final_render', icon='RENDER_STILL')
        if has_render():
            box.operator('cycles_dlss5.final_apply', icon='FILE_REFRESH')
    if has_result():
        row = box.row(align=True)
        row.operator('cycles_dlss5.final_show', icon='IMAGE_DATA')
        row.operator_context = 'INVOKE_DEFAULT'
        row.operator('cycles_dlss5.final_save', text='Сохранить…', icon='FILE_TICK')
    if prefs().final_status:
        import textwrap
        width = max(18, int((context.region.width - 40) / 7)) if context.region else 30
        for line in textwrap.wrap(prefs().final_status, width=width):
            box.label(text=line)
