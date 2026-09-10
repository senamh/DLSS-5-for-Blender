"""Stock Blender postprocessing and sequential viewport preview prototype."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

import bpy
import gpu
from gpu_extras.presets import draw_texture_2d
import numpy as np

from .backend import configure

_active = None


def stop_stock():
    global _active
    operator, _active = _active, None
    if operator is not None:
        operator.cleanup()


class CYCLES_DLSS5_OT_stock(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.stock'
    bl_label = 'Process Render'
    bl_description = 'Create a separate DLSS image using a disposable process; original render is preserved'
    viewport: bpy.props.BoolProperty(default=False)
    _process = None
    _timer = None
    _handle = None
    _log = None
    _folder = None

    def execute(self, context):
        global _active
        if _active is not None:
            if self.viewport and _active.viewport and context.area == _active._area:
                _active._refresh_requested = True
                return {'FINISHED'}
            self.report({'ERROR'}, 'DLSS processing is already active; use Stop Preview')
            return {'CANCELLED'}
        try:
            if context.scene.render.engine != 'CYCLES':
                raise ValueError('Choose Cycles as the render engine')
            if bpy.app.is_job_running('RENDER'):
                raise ValueError('Wait for the current render to finish')
            prefs = context.preferences.addons[__package__].preferences
            runtime = bpy.path.abspath(prefs.runtime_directory)
            bridge = bpy.path.abspath(prefs.bridge_path)
            configure(runtime, bridge, prefs.allow_unrecognized_runtime,
                      bpy.path.abspath(prefs.probe_report), prefs.output_order,
                      prefs.allow_experimental_color)
            self._folder = tempfile.TemporaryDirectory(prefix='blender-dlss5-')
            self._root = Path(self._folder.name)
            self._job = dict(runtime=str(Path(runtime).resolve()), bridge=str(Path(bridge).resolve()),
                             order=prefs.output_order, color_mode='DISPLAY_LINEAR' if self.viewport else 'HDR_TRANSFER', input=str(self._root/'input.npy'),
                             output=str(self._root/'output.npy'))
            self._manager = context.window_manager
            self._area = context.area
            self._capture_error = None
            self._capturing = False
            self._pending = True
            self._refresh_requested = True
            self._inflight = False
            self._sequence = 0
            self._preview_width = int(prefs.preview_width)
            self._preview_image = None
            self._viewport_draws = 0
            if self.viewport:
                if context.area.type != 'VIEW_3D' or context.space_data.shading.type != 'RENDERED':
                    raise ValueError('Start from a 3D View in Rendered shading')
                self._handle = bpy.types.SpaceView3D.draw_handler_add(self.draw_preview, (), 'WINDOW', 'POST_PIXEL')
                context.area.tag_redraw()
            else:
                self.read_render(context)
            self._timer = self._manager.event_timer_add(0.05, window=context.window)
            self._manager.modal_handler_add(self)
            _active = self
            return {'RUNNING_MODAL'}
        except Exception as error:
            self.cleanup()
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

    def read_render(self, context):
        source = bpy.data.images.get('Render Result')
        if source is None:
            raise ValueError('Render a frame with F12 first')
        settings = context.scene.render.image_settings
        previous = (settings.file_format, settings.color_mode, settings.color_depth)
        snapshot = None
        try:
            settings.file_format = 'OPEN_EXR'
            settings.color_mode = 'RGBA'
            settings.color_depth = '32'
            path = str(self._root/'render.exr')
            try:
                source.save_render(path, scene=context.scene)
            except RuntimeError as error:
                if 'does not have any image data' in str(error):
                    raise ValueError('No completed F12 render. For viewport preview use N > DLSS > Capture / Update Preview.') from error
                raise
            snapshot = bpy.data.images.load(path, check_existing=False)
            width, height = snapshot.size
            if width < 1 or height < 1:
                raise ValueError('Render Result is empty; render a frame first')
            frame = np.empty(width*height*4, dtype=np.float32)
            snapshot.pixels.foreach_get(frame)
            self.launch(frame.reshape(height, width, 4))
        finally:
            settings.file_format, settings.color_mode, settings.color_depth = previous
            if snapshot is not None:
                bpy.data.images.remove(snapshot)

    def draw_preview(self):
        if bpy.context.area != self._area:
            return
        if (bpy.context.space_data.shading.type != 'RENDERED' or
                bpy.context.scene.render.engine != 'CYCLES'):
            return
        if self._capturing or self._preview_image is None:
            return
        try:
            texture = gpu.texture.from_image(self._preview_image)
            blend = gpu.state.blend_get()
            depth = gpu.state.depth_test_get()
            try:
                gpu.state.blend_set('NONE')
                gpu.state.depth_test_set('NONE')
                draw_texture_2d(texture, (0, 0), bpy.context.region.width,
                                bpy.context.region.height,
                                is_scene_linear_with_rec709_srgb_target=True)
            finally:
                gpu.state.blend_set(blend)
                gpu.state.depth_test_set(depth)
            self._viewport_draws += 1
        except Exception as error:
            self._capture_error = str(error)

    def capture(self):
        # POST_PIXEL's active framebuffer is Blender's transparent UI overlay,
        # not the composited Cycles view. Screenshot_area forces a redraw and
        # reads the composited window. Hide only our output during that redraw.
        region = next(r for r in self._area.regions if r.type == 'WINDOW')
        path = str(self._root/'viewport-capture.png')
        snapshot = None
        self._capturing = True
        self._area.tag_redraw()
        try:
            with bpy.context.temp_override(area=self._area, region=region):
                if bpy.ops.screen.screenshot_area(filepath=path) != {'FINISHED'}:
                    raise ValueError('Blender could not capture the viewport')
            snapshot = bpy.data.images.load(path, check_existing=False)
            snapshot.colorspace_settings.name = 'Non-Color'
            width, height = snapshot.size
            pixels = np.empty(width*height*4, dtype=np.float32)
            snapshot.pixels.foreach_get(pixels)
            pixels = pixels.reshape(height, width, 4)
            # Screenshot covers the editor, including headers. Select WINDOW.
            sx, sy = width/self._area.width, height/self._area.height
            x = round((region.x-self._area.x)*sx)
            y = round((region.y-self._area.y)*sy)
            w, h = round(region.width*sx), round(region.height*sy)
            frame = pixels[y:y+h, x:x+w].copy()
            height, width = frame.shape[:2]
            if not width or not height:
                raise ValueError('Captured viewport is empty')
            self._preview_width = int(bpy.context.preferences.addons[__package__].preferences.preview_width)
            if self._preview_width and width > self._preview_width:
                out_w = self._preview_width
                out_h = max(1, round(height*out_w/width))
                xs = np.linspace(0, width-1, out_w).astype(np.intp)
                ys = np.linspace(0, height-1, out_h).astype(np.intp)
                frame = frame[ys[:, None], xs[None, :], :].copy()
            rgb = np.maximum(frame[:, :, :3], 0)
            frame[:, :, :3] = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
            # The preview must cover the scene; overlay-buffer alpha is not
            # scene transparency. Final render alpha remains untouched.
            frame[:, :, 3] = 1.0
            self._captured = frame
            self._pending = False
        finally:
            self._capturing = False
            if snapshot is not None:
                bpy.data.images.remove(snapshot)
            self._area.tag_redraw()

    def launch(self, frame):
        from .styles import values
        self._job['settings'] = values(bpy.context.scene.dlss5_style)
        self._source_frame = frame.copy()
        np.save(self._job['input'], frame, allow_pickle=False)
        path = self._root/'job.json'
        temporary = self._root/'job.tmp'
        temporary.write_text(json.dumps(self._job), encoding='utf-8')
        temporary.replace(path)
        if self._process is None:
            self._log = (self._root/'worker.log').open('w', encoding='utf-8')
            command = [bpy.app.binary_path, '--background', '--factory-startup', '--python-exit-code', '1',
                       '--python', str(Path(__file__).with_name('stock_worker.py')), '--', str(path)]
            if self.viewport:
                command.append('--serve')
            self._process = subprocess.Popen(command, stdout=self._log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if self.viewport:
            self._sequence += 1
            request = self._root/'request.tmp'
            request.write_text(json.dumps({'sequence': self._sequence}), encoding='utf-8')
            request.replace(self._root/f'request-{self._sequence}.json')
        self._inflight = True
        self._started = time.monotonic()

    def modal(self, context, event):
        global _active
        if _active is not self:
            return {'CANCELLED'}
        if event.type == 'ESC':
            stop_stock()
            return {'CANCELLED'}
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}
        try:
            if self._capture_error:
                raise ValueError(self._capture_error)
            if self.viewport and self._area not in list(context.screen.areas):
                raise ValueError('Source viewport was closed')
            if self.viewport and (self._area.type != 'VIEW_3D' or
                    self._area.spaces.active.shading.type != 'RENDERED' or
                    context.scene.render.engine != 'CYCLES' or bpy.app.is_job_running('RENDER')):
                stop_stock()
                return {'CANCELLED'}
            if not self._inflight:
                if self.viewport:
                    automatic = context.preferences.addons[__package__].preferences.preview_auto
                    if not automatic and not self._refresh_requested:
                        return {'RUNNING_MODAL'}
                if self.viewport and self._pending:
                    self.capture()
                if self.viewport and not self._pending:
                    self.launch(self._captured)
                    self._refresh_requested = False
                return {'RUNNING_MODAL'}
            if time.monotonic() - self._started > 120:
                raise ValueError('DLSS worker exceeded 120 seconds')
            done = self._root/f'done-{self._sequence}.json'
            try:
                ready = (self.viewport and done.exists() and
                         json.loads(done.read_text(encoding='utf-8'))['sequence'] == self._sequence)
            except PermissionError:
                return {'RUNNING_MODAL'}
            if self._process.poll() is None and not ready:
                if time.monotonic() - self._started > 120:
                    raise ValueError('DLSS worker exceeded 120 seconds')
                return {'RUNNING_MODAL'}
            if self._process.poll() is not None and (self.viewport or self._process.returncode):
                detail = (self._root/'worker.log').read_text(encoding='utf-8', errors='replace')[-1500:]
                raise ValueError('DLSS worker failed: '+detail)
            frame = np.load(self._job['output'], allow_pickle=False)
            if self.viewport:
                for consumed in (done, self._root/f'request-{self._sequence}.json'):
                    try:
                        consumed.unlink(missing_ok=True)
                    except PermissionError:
                        pass  # TemporaryDirectory removes any locked leftovers on stop.
            if frame.shape != self._source_frame.shape or not np.isfinite(frame).all():
                raise ValueError('Invalid DLSS output')
            height, width, _ = frame.shape
            change = float(np.mean(np.abs(frame[:, :, :3]-self._source_frame[:, :, :3])))
            evidence = os.environ.get('CYCLES_DLSS5_CAPTURE_EVIDENCE')
            if self.viewport and evidence and self._sequence in (1, 2, 10, 40):
                folder = Path(evidence)
                folder.mkdir(parents=True, exist_ok=True)
                np.save(folder/f'input-{self._sequence}.npy', self._source_frame, allow_pickle=False)
                np.save(folder/f'output-{self._sequence}.npy', frame, allow_pickle=False)
            if self.viewport:
                mode = context.preferences.addons[__package__].preferences.preview_compare
                if mode == 'ORIGINAL':
                    frame = self._source_frame.copy()
                elif mode == 'SPLIT':
                    frame[:, :width//2, :] = self._source_frame[:, :width//2, :]
            else:
                original = bpy.data.images.new('DLSS Original Render', width=width, height=height,
                                               alpha=True, float_buffer=True)
                original.pixels.foreach_set(self._source_frame.ravel())
                original.update()
                original.use_view_as_render = True
            name = 'DLSS Viewport Preview' if self.viewport else 'DLSS Render'
            target = bpy.data.images.get(name)
            if target is None:
                target = bpy.data.images.new(name, width, height, alpha=True, float_buffer=True)
                target['cycles_dlss5_output'] = True
            elif not target.get('cycles_dlss5_output'):
                raise ValueError(f'Image name {name} is already used; rename it first')
            elif tuple(target.size) != (width, height):
                target.scale(width, height)
            target.pixels.foreach_set(frame.ravel())
            target.update()
            target.use_view_as_render = not self.viewport
            target['dlss_updates'] = int(target.get('dlss_updates', 0)) + 1
            target['dlss_worker_seconds'] = time.monotonic() - self._started
            target['dlss_worker_pid'] = self._process.pid
            target['dlss_mean_change'] = change
            target['dlss_viewport_draws'] = self._viewport_draws
            if self.viewport:
                self._preview_image = target
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
                if area.type == 'IMAGE_EDITOR' and not self.viewport:
                    area.spaces.active.image = target
                    area.tag_redraw()
            self._inflight = False
            if self.viewport:
                self._pending = True
                self._area.tag_redraw()
                return {'RUNNING_MODAL'}
            self.report({'INFO'}, 'DLSS Render is ready in Image Editor; use Image > Save As')
            stop_stock()
            return {'FINISHED'}
        except Exception as error:
            self.report({'ERROR'}, str(error))
            stop_stock()
            return {'CANCELLED'}

    def cleanup(self):
        if self._handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
            try:
                self._area.tag_redraw()
            except ReferenceError:
                pass
        if self._process is not None and self._process.poll() is None:
            (self._root/'stop').touch()
            try:
                self._process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        if self._timer is not None:
            self._manager.event_timer_remove(self._timer)
            self._timer = None
        if self._log is not None:
            self._log.close()
            self._log = None
        if self._folder is not None:
            self._folder.cleanup()
            self._folder = None


class CYCLES_DLSS5_OT_stock_stop(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.stock_stop'
    bl_label = 'Stop Preview'

    def execute(self, context):
        stop_stock()
        return {'FINISHED'}


class CYCLES_DLSS5_PT_stock_view(bpy.types.Panel):
    bl_label = 'DLSS Preview'
    bl_idname = 'CYCLES_DLSS5_PT_stock_view'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'DLSS Dev'

    @classmethod
    def poll(cls, context):
        addon = context.preferences.addons.get(__package__)
        return addon is not None and addon.preferences.show_advanced

    def draw(self, context):
        prefs = context.preferences.addons[__package__].preferences
        self.layout.prop(prefs, 'preview_width')
        self.layout.prop(prefs, 'preview_compare')
        self.layout.label(text='Result appears in this 3D View')
        self.layout.label(text='Split: original left, DLSS right')
        self.layout.label(text='Display capture; overlays included')
        self.layout.label(text='Snapshot preview; update after editing')
        self.layout.prop(prefs, 'preview_auto')
        self.layout.label(text='F12 is not required for this preview')
        preview = bpy.data.images.get('DLSS Viewport Preview')
        if preview and preview.get('cycles_dlss5_output'):
            self.layout.label(text=f"Updates: {preview.get('dlss_updates', 0)}; processing: {preview.get('dlss_worker_seconds', 0):.2f}s")
            self.layout.label(text=f"Pixel change: {preview.get('dlss_mean_change', 0):.5f}")
        self.layout.operator('cycles_dlss5.stock', text='Capture / Update Preview').viewport = True
        self.layout.operator('cycles_dlss5.stock_stop')
