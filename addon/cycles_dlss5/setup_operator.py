"""Explicit local setup and useful diagnostics on machines without the runtime."""
import bpy
from . import runtime_setup


class CYCLES_DLSS5_OT_setup_check(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.setup_check'
    bl_label = 'Проверить установку и GPU'

    def execute(self, context):
        from . import shortcuts
        shortcuts.audit()
        prefs = context.preferences.addons[__package__].preferences
        prefs.setup_status = runtime_setup.gpu_info()
        try:
            from .final_render import runtime_paths, check_selected_runtime
            if prefs.experimental_native_session:
                check_selected_runtime()
                prefs.setup_status += '\nЭкспериментальный native runtime: SHA256 проверены (SDR).'
            else:
                host, folder = runtime_paths()
                prefs.setup_status += '\n' + runtime_setup.verify_files(host, folder)
            self.report({'INFO'}, 'Файлы проверены; запустите эффект для проверки NR на GPU')
            return {'FINISHED'}
        except Exception as error:
            prefs.setup_status += '\n' + str(error)
            self.report({'WARNING'}, str(error))
            return {'CANCELLED'}
