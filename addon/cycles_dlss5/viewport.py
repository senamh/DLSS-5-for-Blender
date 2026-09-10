"""Same-project asynchronous NR viewport. Not a game-rate temporal integration."""
import json
from pathlib import Path
import tempfile
import time
import bpy
from bpy.app.handlers import persistent
import gpu
import numpy as np
from gpu_extras.presets import draw_texture_2d
from gpu_extras.batch import batch_for_shader
from .frame_job import FrameJob
from .render_payload import prepare_image, publish_image
from .styles import values
from .preview_state import same_view, matrix_key

_session = None
_target = None


def stop(keep_target=False):
    global _session, _target
    if not keep_target:
        _target = None
    session, _session = _session, None
    if bpy.app.timers.is_registered(tick):
        bpy.app.timers.unregister(tick)
    if session is not None:
        if session.get('worker') is not None:
            session['worker'].close()
        if session.get('handle') is not None:
            bpy.types.SpaceView3D.draw_handler_remove(session['handle'], 'WINDOW')
        try:
            session['area'].tag_redraw()
        except ReferenceError:
            pass


def target(context):
    from .preview_launch import viewport_source
    return viewport_source(context)


def valid(session):
    try:
        return (session['window'] in list(bpy.context.window_manager.windows)
                and session['area'] in list(session['window'].screen.areas)
                and session['area'].type == 'VIEW_3D'
                and session['window'].scene == session['scene'])
    except ReferenceError:
        return False


def visible_rect(area):
    region = next(r for r in area.regions if r.type == 'WINDOW')
    left, bottom, right, top = region.x, region.y, region.x + region.width, region.y + region.height
    for other in area.regions:
        if other.type not in {'UI', 'TOOLS'} or other.width <= 1:
            continue
        if other.x > left:
            right = min(right, other.x)
        else:
            left = max(left, other.x + other.width)
    return region, (left - region.x, bottom - region.y, right - left, top - bottom)


def key(session):
    space = session['area'].spaces.active
    scene = session['scene']
    region, rect = visible_rect(session['area'])
    return (matrix_key(space.region_3d.view_matrix),
            matrix_key(space.region_3d.window_matrix), rect,
            scene.frame_current, tuple(values(scene.dlss5_style).values()),
            scene.view_settings.view_transform, scene.view_settings.look,
            scene.view_settings.exposure, scene.view_settings.gamma,
            space.shading.type, session.get('revision', 0))


def draw():
    session = _session
    if (session is None or not valid(session) or bpy.context.area != session['area']
            or session.get('capturing') or session.get('image') is None):
        return
    if session['mode'] == 'PREVIEW' and not same_view(session.get('published_key'), key(session)):
        return
    try:
        region, (x, y, width, height) = visible_rect(session['area'])
        backdrop = (x, y, width, height)
        image = session['image']
        if session['mode'] == 'FINAL':
            scale = min(width / image.size[0], height / image.size[1])
            w, h = image.size[0] * scale, image.size[1] * scale
            x, y = x + (width - w) / 2, y + (height - h) / 2
            width, height = w, h
        blend, depth = gpu.state.blend_get(), gpu.state.depth_test_get()
        try:
            gpu.state.blend_set('NONE')
            gpu.state.depth_test_set('NONE')
            if session['mode'] == 'FINAL':
                bx, by, bw, bh = backdrop
                shader = gpu.shader.from_builtin('UNIFORM_COLOR')
                batch = batch_for_shader(shader, 'TRIS', {'pos': ((bx, by), (bx + bw, by),
                                         (bx + bw, by + bh), (bx, by + bh))}, indices=((0, 1, 2), (2, 3, 0)))
                shader.uniform_float('color', (0.025, 0.025, 0.025, 1))
                batch.draw(shader)
                gpu.state.blend_set('ALPHA')
            draw_texture_2d(gpu.texture.from_image(image), (x, y), width, height,
                            is_scene_linear_with_rec709_srgb_target=True)
        finally:
            gpu.state.blend_set(blend)
            gpu.state.depth_test_set(depth)
        session['draws'] = session.get('draws', 0) + 1
    except Exception as error:
        session['error'] = str(error)


def start(context, mode='PREVIEW', image=None):
    global _session, _target
    from .final_render import check_selected_runtime
    if hasattr(bpy.types, 'DLSS5_OT_control'):
        raise ValueError('Откройте обычный Blender: экранный ReShade иначе обработает изображение повторно')
    if mode == 'PREVIEW':
        check_selected_runtime()
        if context.scene.display_settings.display_device != 'sRGB':
            raise ValueError('Viewport NR поддерживает только sRGB SDR')
    previous = _session or _target
    reuse = previous is not None and valid(previous) and previous['scene'] == context.scene
    window, area = ((previous['window'], previous['area']) if reuse else
                    target(context))
    stop()
    if mode == 'PREVIEW':
        area.spaces.active.shading.type = 'RENDERED'
    _session = dict(window=window, area=area, scene=window.scene, mode=mode, image=image,
                    job=None, worker=None, revision=0, changed=time.monotonic(), published_key=None,
                    progress=0, phase='WAITING')
    _target = {field: _session[field] for field in ('window', 'area', 'scene')}
    _session['observed_key'] = key(_session)
    _session['handle'] = bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_PIXEL')
    area.tag_redraw()
    bpy.app.timers.register(tick, first_interval=.2)
    return True


def capture(session, folder):
    """Capture native rendered view, crop editor chrome, never capture our overlay."""
    area, window = session['area'], session['window']
    region, (rx, ry, rw, rh) = visible_rect(area)
    if min(rw, rh) < 96:
        raise ValueError('Увеличьте viewport: минимум 96 пикселей по каждой стороне')
    space = area.spaces.active
    overlay, gizmo = space.overlay.show_overlays, space.show_gizmo
    session['capturing'] = True
    image = None
    try:
        space.overlay.show_overlays = False
        space.show_gizmo = False
        area.tag_redraw()
        path = str(folder / 'viewport.png')
        with bpy.context.temp_override(window=window, area=area, region=region):
            if bpy.ops.screen.screenshot_area(filepath=path) != {'FINISHED'}:
                raise ValueError('Blender не смог получить кадр viewport')
        image = bpy.data.images.load(path, check_existing=False)
        image.colorspace_settings.name = 'Non-Color'
        w, h = image.size
        pixels = np.empty(w * h * 4, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        sx, sy = w / area.width, h / area.height
        x, y = round((region.x - area.x + rx) * sx), round((region.y - area.y + ry) * sy)
        frame = pixels.reshape(h, w, 4)[y:y + round(rh * sy), x:x + round(rw * sx)]
        # Bound worker input; this is preview resolution, not final export resolution.
        h, w = frame.shape[:2]
        scale = min(1, 1280 / w, 1280 / h)
        ow, oh = int(w * scale), int(h * scale)
        frame = frame[np.linspace(0, h - 1, oh).astype(int)[:, None],
                      np.linspace(0, w - 1, ow).astype(int)[None, :]].copy()
        frame[:, :, 3] = 1
        rgba = np.rint(np.clip(frame[::-1], 0, 1) * 255).astype(np.uint8)
        return prepare_image(folder, rgba.tobytes(), ow, oh)
    finally:
        if image is not None:
            bpy.data.images.remove(image)
        space.overlay.show_overlays, space.show_gizmo = overlay, gizmo
        # Flush redraw bookkeeping while self-generated changes are suppressed.
        with bpy.context.temp_override(window=window, area=area, region=region):
            window.view_layer.update()
        session['capturing'] = False
        area.tag_redraw()


def tick():
    session = _session
    if session is None:
        return None
    try:
        if not valid(session):
            stop()
            return None
        if session.get('error'):
            raise ValueError(session['error'])
        if session['mode'] == 'FINAL':
            return .5
        from .final_render import create_job, _active, _pending
        if _active is not None or _pending is not None or bpy.app.is_job_running('RENDER'):
            return .2
        current = key(session)
        if current != session['observed_key']:
            session['observed_key'], session['changed'] = current, time.monotonic()
            if session['job'] is None:
                session['progress'], session['phase'] = 0, 'WAITING'
            session['area'].tag_redraw()
        job = session['job']
        if job is not None:
            percent = job.progress()
            if percent != session['progress']:
                session['progress'] = percent
                session['area'].tag_redraw()
            code = job.poll()
            if code is None:
                return .2
            try:
                report = job.finish(code, diagnostics=False)
                report['settings'] = session['settings']
                report['kind'] = 'asynchronous viewport snapshot; image-only NR'
                # Do not starve publication when depsgraph keeps notifying us.
                # The snapshot remains labelled pending if a newer edit exists.
                if same_view(current, session['job_key']):
                    session['publishing'] = True
                    path = job.work / 'preview.png'
                    publish_image(job, report, path)
                    image = bpy.data.images.load(str(path), check_existing=False)
                    image.name = 'DLSS Viewport'
                    image.colorspace_settings.name = 'sRGB'
                    image.use_view_as_render = False
                    image.pack()
                    image['dlss5_report'] = json.dumps(report)
                    previous = session['image']
                    session['image'] = image
                    session['published_key'] = session['job_key']
                    session['published_signature'] = session['job_signature']
                    session['progress'] = 100
                    session['phase'] = 'READY' if current == session['job_key'] else 'WAITING'
                    session['updates'] = session.get('updates', 0) + 1
                    if previous is not None and previous.users == 0:
                        bpy.data.images.remove(previous)
                    session['area'].tag_redraw()
            finally:
                if session.get('publishing'):
                    with bpy.context.temp_override(window=session['window'], area=session['area']):
                        session['window'].view_layer.update()
                    session['publishing'] = False
                session['job'] = None
            return .2
        # Keep first-frame settling time; style-only edits need no Cycles restart.
        published = session.get('published_key')
        style_only = published is not None and published[:4] + published[5:] == current[:4] + current[5:]
        delay = .4 if style_only else 1.5
        if session.get('published_key') == current or time.monotonic() - session['changed'] < delay:
            return .2
        if session['area'].spaces.active.shading.type != 'RENDERED':
            return .2
        with tempfile.TemporaryDirectory(prefix='dlss5-viewport-', ignore_cleanup_errors=True) as folder:
            session['phase'], session['progress'] = 'CAPTURING', 5
            meta = capture(session, Path(folder))
            session['settings'], session['job_key'] = values(session['scene'].dlss5_style), key(session)
            session['job_signature'] = (meta['files']['color.rgba8']['sha256'], tuple(session['settings'].items()))
            if session.get('published_signature') == session['job_signature'] and session.get('image') is not None:
                session['published_key'] = session['job_key']
                session['observed_key'] = session['job_key']
                session['phase'], session['progress'] = 'READY', 100
                session['area'].tag_redraw()
                return .2
            if session['worker'] is None:
                session['worker'] = create_job(folder, session['settings'])
            else:
                session['worker'].prepare(folder, session['settings'])
            session['job'] = session['worker']
            session['job'].start()
            session['phase'], session['progress'] = 'PROCESSING', 25
            session['area'].tag_redraw()
        return .2
    except Exception as error:
        message = 'Viewport NR: ' + str(error)
        stop()
        from .final_render import status
        status(message)
        return None


@persistent
def scene_changed(scene, depsgraph):
    if (_session is None or _session['mode'] != 'PREVIEW' or _session.get('capturing')
            or _session.get('publishing')):
        return
    if scene == _session['scene'] and any(isinstance(update.id, (bpy.types.Object, bpy.types.Material,
            bpy.types.World, bpy.types.Mesh, bpy.types.Light, bpy.types.NodeTree))
            and (update.is_updated_transform or update.is_updated_geometry or update.is_updated_shading)
            for update in depsgraph.updates):
        _session['revision'] += 1


class CYCLES_DLSS5_OT_viewport(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.viewport'
    bl_label = 'Эффект во вьюпорте'
    bl_description = 'Обновляемый NR предпросмотр после паузы; те же параметры, что у рендера, не realtime FPS'

    def execute(self, context):
        try:
            start(context)
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}


class CYCLES_DLSS5_OT_viewport_stop(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.viewport_stop'
    bl_label = 'Вернуться к сцене'

    def execute(self, context):
        stop()
        return {'FINISHED'}
