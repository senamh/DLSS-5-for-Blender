"""Read the saved user scene in an isolated process; never save it."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time
import runpy
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
runpy.run_path(str(Path(bpy.app.binary_path).with_name('start_preview.py')))
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
    area.tag_redraw()
    elapsed=time.monotonic()-started
    if elapsed>16 and 'with' not in done:
        key(117,'depth with overlays');done.add('with')
    if elapsed>20 and 'off' not in done:
        area.spaces.active.overlay.show_overlays=False;done.add('off')
    if elapsed>26 and 'without' not in done:
        key(117,'depth without overlays');done.add('without')
    if elapsed>30:
        (out/'audit.json').write_text(json.dumps({'saved':False,'events':events,
            'area':{'x':area.x,'y':area.y,'width':area.width,'height':area.height},
            'window':{'width':window.width,'height':window.height},
            'engine':scene.render.engine,'depth_view':1},indent=2))
        bpy.ops.wm.quit_blender();return None
    return .05
bpy.app.timers.register(tick,first_interval=1)

