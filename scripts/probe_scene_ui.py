"""Read the saved user scene in an isolated process; never save it."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time
import bpy
from mathutils import Quaternion

out=Path(sys.argv[sys.argv.index('--')+1])
project=Path(r'C:\Users\User\Downloads\Apple vision pro.blend')
if not project.exists():
    project=Path(r'C:\Users\User\Downloads\Apple vision pro\Apple vision pro.blend')
assert project.exists(),'Saved scene not found'
# Preserve the single startup window. Saved workspace/window restoration caused
# ReShade to instantiate an additional runtime during scene load.
bpy.context.preferences.filepaths.use_load_ui=False
bpy.ops.wm.open_mainfile(filepath=str(project),load_ui=False,use_scripts=False)
scene=bpy.context.scene
scene.render.engine='CYCLES'
scene.cycles.preview_samples=16
scene.cycles.use_preview_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX'
prefs.get_devices()
for d in prefs.devices:
    d.use=d.type=='OPTIX'
scene.cycles.device='GPU'
window=next(w for w in bpy.context.window_manager.windows if w.screen and
    any(a.type=='VIEW_3D' for a in w.screen.areas))
area=next(a for a in window.screen.areas if a.type=='VIEW_3D')
area.spaces.active.shading.type='RENDERED'
region=area.spaces.active.region_3d
if scene.camera:
    region.view_perspective='CAMERA'
started=time.monotonic()
ticks=0
events=[]
user32=ctypes.WinDLL('user32',use_last_error=True)
user32.GetForegroundWindow.restype=ctypes.c_void_p
user32.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
def key(vk,label):
    # Address only this process's visible Blender window. Do not send global
    # keyboard input into whichever application the user is working in.
    candidates=[]
    callback_type=ctypes.WINFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_ssize_t)
    user32.IsWindowVisible.argtypes=[ctypes.c_void_p]
    def collect(hwnd,_):
        pid=ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value==os.getpid() and user32.IsWindowVisible(hwnd): candidates.append(hwnd)
        return 1
    user32.EnumWindows(callback_type(collect),0)
    if not candidates:
        events.append({'event':label,'skipped':'no visible process window'})
        return
    hwnd=candidates[0]
    user32.PostMessageW.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_size_t,ctypes.c_ssize_t]
    user32.PostMessageW(hwnd,0x100,vk,1)
    def release():
        user32.PostMessageW(hwnd,0x101,vk,0xC0000001)
    bpy.app.timers.register(release,first_interval=.2)
    events.append({'event':label,'sent':True})
done=set()
def tick():
    global ticks
    ticks+=1
    area.tag_redraw()
    elapsed=time.monotonic()-started
    if elapsed>6 and 'reload' not in done:
        key(0x76,'F7 delayed effect loading')
        done.add('reload')
    if elapsed>15 and 'frame' not in done:
        with bpy.context.temp_override(window=window,area=area):
            bpy.ops.screen.screenshot(filepath=str(out/'blender-frame.png'))
        key(0x75,'ReShade F6 screenshot')
        done.add('frame')
    if elapsed>18 and 'rotate' not in done:
        # Change only this process's view, never camera/object transforms.
        region.view_perspective='PERSP'
        region.view_rotation=Quaternion((0,0,1),.15)@region.view_rotation
        done.add('rotate')
    if elapsed>25:
        with bpy.context.temp_override(window=window,area=area):
            bpy.ops.screen.screenshot(filepath=str(out/'rotated-frame.png'))
        (out/'ui.json').write_text(json.dumps({'project':str(project),'saved':False,'ticks':ticks,
            'view_rotation_exercised':'rotate' in done,'events':events,
            'scene_engine':scene.render.engine,'cycles_device':scene.cycles.device,
            'shader_compilation_method':bpy.context.preferences.system.shader_compilation_method,
            'shader_workers':bpy.context.preferences.system.gpu_shader_workers},indent=2))
        bpy.ops.wm.quit_blender()
        return None
    return .05
bpy.app.timers.register(tick,first_interval=1)

