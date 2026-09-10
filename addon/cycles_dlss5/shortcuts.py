"""Single-key fallbacks; preserve occupied Blender and other-addon bindings."""
import bpy

_keymaps = []
BINDINGS = (('cycles_dlss5.viewport_toggle', 'F6'),
            ('cycles_dlss5.final_render', 'F7'),
            ('cycles_dlss5.cancel', 'F8'))
conflicts = {}


def audit():
    conflicts.clear()
    configs = bpy.context.window_manager.keyconfigs
    for _, own in _keymaps:
        found = []
        for config in (configs.default, configs.user, configs.addon):
            if config is None:
                continue
            for keymap in config.keymaps:
                for item in keymap.keymap_items:
                    if item.idname.startswith('cycles_dlss5.') or not item.active:
                        continue
                    if item.type == own.type and (item.any or not (item.ctrl or item.alt or item.shift or item.oskey)):
                        found.append(keymap.name + ': ' + item.idname)
        if hasattr(bpy.types, 'DLSS5_OT_control'):
            found.append('Старый экранный ReShade')
        own.active = not found
        if found:
            conflicts[own.type] = ', '.join(sorted(set(found)))
    return None


class CYCLES_DLSS5_OT_viewport_toggle(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.viewport_toggle'
    bl_label = 'Переключить эффект во вьюпорте'

    def execute(self, context):
        from . import viewport, final_render
        if viewport._session is not None:
            viewport.stop()
            return {'FINISHED'}
        if final_render._active is not None or final_render._pending is not None or bpy.app.is_job_running('RENDER'):
            self.report({'WARNING'}, 'Дождитесь завершения рендера / NR')
            return {'CANCELLED'}
        return bpy.ops.cycles_dlss5.viewport()


class CYCLES_DLSS5_OT_cancel(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.cancel'
    bl_label = 'Остановить NR и предпросмотр'

    def execute(self, context):
        from . import viewport
        viewport.stop()
        return bpy.ops.cycles_dlss5.final_stop()


CLASSES = (CYCLES_DLSS5_OT_viewport_toggle, CYCLES_DLSS5_OT_cancel)


def register():
    if _keymaps:
        return
    config = bpy.context.window_manager.keyconfigs.addon
    if config is None:
        return
    keymap = config.keymaps.new(name='3D View', space_type='VIEW_3D')
    for operator, key in BINDINGS:
        item = keymap.keymap_items.new(operator, type=key, value='PRESS')
        _keymaps.append((keymap, item))
    audit()
    # Factory/user keymaps can still be initializing while extensions register.
    if not bpy.app.background and not bpy.app.timers.is_registered(audit):
        bpy.app.timers.register(audit, first_interval=1, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(audit):
        bpy.app.timers.unregister(audit)
    for keymap, item in _keymaps:
        keymap.keymap_items.remove(item)
    _keymaps.clear()
    conflicts.clear()
