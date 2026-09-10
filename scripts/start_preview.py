"""Native Blender controls for the upstream DLSS5 stack with guarded OpenGL view compatibility."""
import ctypes
import os
from pathlib import Path
import runpy
import sys
import bpy

window=next(w for w in bpy.context.window_manager.windows if w.screen)
with bpy.context.temp_override(window=window):
    runpy.run_path(str(Path(__file__).with_name('start_ready.py')))
bpy.context.preferences.filepaths.use_load_ui=False
root=Path(bpy.app.binary_path).parent
control_paths = (Path(__file__).resolve().parents[1] / 'addon/cycles_dlss5/preview_controls.py',
                 root / 'dlss5_addons/cycles_dlss5/preview_controls.py')
control_path = next((path for path in control_paths if path.is_file()), None)
if control_path is None:
    raise RuntimeError('Update the bundled DLSS addon: preview_controls.py is missing')
ACTION_KEYS = runpy.run_path(str(control_path))['ACTION_KEYS']

def send_key(key):
    if key not in (*ACTION_KEYS.values(), 117,118,121):
        return False
    api=ctypes.WinDLL('user32',use_last_error=True)
    api.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
    api.IsWindowVisible.argtypes=[ctypes.c_void_p]
    api.PostMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
    api.GetForegroundWindow.restype=ctypes.c_void_p
    candidates=[]
    callback_type=ctypes.WINFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_ssize_t)
    api.EnumWindows.argtypes=[callback_type,ctypes.c_ssize_t]
    def collect(hwnd,_):
        pid=ctypes.c_ulong()
        api.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value==os.getpid() and api.IsWindowVisible(hwnd): candidates.append(hwnd)
        return 1
    api.EnumWindows(callback_type(collect),0)
    if not candidates: return False
    foreground=api.GetForegroundWindow()
    hwnd=foreground if foreground in candidates else candidates[0]
    if not api.PostMessageW(hwnd,0x100,key,1):
        return False
    def release(): api.PostMessageW(hwnd,0x101,key,0xC0000001)
    bpy.app.timers.register(release,first_interval=.2)
    return True

class DLSS5_OT_control(bpy.types.Operator):
    bl_idname='dlss5.control'
    bl_label='DLSS 5 control'
    action:bpy.props.EnumProperty(items=(
        ('TOGGLE','Включить / выключить DLSS',''),
        ('RELOAD','Обновить эффекты',''),
        ('OVERLAY','Настройки ReShade',''),
        ('SCREENSHOT','Снимок экрана','')))
    def execute(self,context):
        return {'FINISHED'} if send_key(ACTION_KEYS[self.action]) else {'CANCELLED'}

class DLSS5_PT_preview(bpy.types.Panel):
    bl_label='DLSS 5 Preview'
    bl_idname='DLSS5_PT_preview'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='DLSS 5'
    def draw(self,context):
        layout=self.layout
        layout.operator('dlss5.control',text='Включить / выключить DLSS').action='TOGGLE'
        layout.operator('dlss5.control',text='Открыть / закрыть настройки').action='OVERLAY'
        layout.operator('dlss5.control',text='Обновить после изменения окна').action='RELOAD'
        layout.operator('dlss5.control',text='Снимок экрана с эффектом').action='SCREENSHOT'
        layout.label(text='Если меню блокирует кнопки, закройте его клавишей F8.')
        layout.label(text='F10 / F7 / F6 больше не назначены DLSS.')
        layout.operator_context='INVOKE_DEFAULT'
        layout.operator('render.render',text='Обычный рендер Blender')
        layout.label(text='Экранный DLSS не применяется к обычному рендеру.')

legacy_operator=getattr(bpy.types,'DLSS5_OT_upstream_key',None)
if legacy_operator:
    bpy.utils.unregister_class(legacy_operator)
for cls in (DLSS5_OT_control,DLSS5_PT_preview):
    old=getattr(bpy.types,cls.__name__,None)
    if old:
        bpy.utils.unregister_class(old)
    bpy.utils.register_class(cls)

# Deferred loading avoids compiling injected effects while Blender initializes.
def initial_reload():
    send_key(ACTION_KEYS['RELOAD'])
    return None
bpy.app.timers.register(initial_reload,first_interval=6)

# The installed desktop launcher can use the same addon UI as scene-copy previews.
# It is bundled Python only; the native runtime is left untouched.
bundled_addons = root / 'dlss5_addons'
if (bundled_addons / 'cycles_dlss5' / '__init__.py').is_file():
    import addon_utils
    if str(bundled_addons) not in sys.path:
        sys.path.append(str(bundled_addons))
    try:
        if not hasattr(bpy.types, 'CYCLES_DLSS5_PT_preview_launcher'):
            addon_utils.enable('cycles_dlss5', default_set=True)
        if hasattr(bpy.types, 'CYCLES_DLSS5_PT_preview_launcher'):
            bpy.utils.unregister_class(DLSS5_PT_preview)
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.spaces.active.show_region_ui = True
    except Exception as error:
        print('DLSS5 addon UI could not load:', error, flush=True)
