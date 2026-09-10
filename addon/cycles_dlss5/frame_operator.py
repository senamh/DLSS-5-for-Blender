"""Blender UI for the upstream static-frame host; no replacement of Render Result."""
import os
from pathlib import Path
import bpy
from .frame_job import FrameJob

_active = None


def stop_frame():
    global _active
    operator, _active = _active, None
    if operator is not None:
        operator.cleanup()


class CYCLES_DLSS5_OT_frame(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.frame'
    bl_label = 'Process Cycles Frame Payload'
    bl_description = 'Select exported payload.json; process real guides in the upstream host (static SDR only)'
    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default='payload.json', options={'HIDDEN'})
    _job = None
    _timer = None

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        global _active
        if _active is not None:
            self.report({'ERROR'}, 'A frame job is already running; press Escape to cancel')
            return {'CANCELLED'}
        try:
            if os.name != 'nt':
                raise ValueError('The upstream frame host requires Windows')
            if bpy.app.is_job_running('RENDER'):
                raise ValueError('Wait for the current render to finish')
            prefs = context.preferences.addons[__package__].preferences
            if not prefs.frame_host or not prefs.frame_runtime_directory:
                raise ValueError('Set Frame Host and Preview Runtime Folder in addon preferences')
            path = Path(bpy.path.abspath(self.filepath))
            if path.name != 'payload.json':
                raise ValueError('Select payload.json from the Cycles guide export')
            self._job = FrameJob(path.parent, bpy.path.abspath(prefs.frame_host),
                                 bpy.path.abspath(prefs.frame_runtime_directory))
            self._job.start()
            self._manager = context.window_manager
            self._timer = self._manager.event_timer_add(.1, window=context.window)
            self._manager.modal_handler_add(self)
            _active = self
            return {'RUNNING_MODAL'}
        except Exception as error:
            self.cleanup()
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

    def modal(self, context, event):
        if _active is not self:
            return {'CANCELLED'}
        if event.type == 'ESC':
            stop_frame()
            return {'CANCELLED'}
        if event.type != 'TIMER' or event.timer != self._timer:
            return {'PASS_THROUGH'}
        image = None
        try:
            code = self._job.poll()
            if code is None:
                return {'RUNNING_MODAL'}
            report = self._job.finish(code)
            image = bpy.data.images.load(str(self._job.work / 'after.png'), check_existing=False)
            image.name = 'DLSS Verified Cycles Frame'
            image.colorspace_settings.name = 'sRGB'
            image.use_view_as_render = False  # Host returns display-referred SDR.
            image['dlss_nr_confirmed'] = report['nr_confirmed']
            image['dlss_output_sha256'] = report['output_sha256']
            image.pack()  # Keep output alive after the disposable job is removed.
            for area in context.screen.areas:
                if area.type == 'IMAGE_EDITOR':
                    area.spaces.active.image = image
                    area.tag_redraw()
            stop_frame()
            self.report({'INFO'}, 'Verified Cycles frame ready in Image Editor (SDR); Image > Save As')
            return {'FINISHED'}
        except Exception as error:
            if image is not None:
                bpy.data.images.remove(image)
            stop_frame()
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

    def cleanup(self):
        try:
            if self._job is not None:
                self._job.close()
                self._job = None
        finally:
            if self._timer is not None:
                self._manager.event_timer_remove(self._timer)
                self._timer = None
