"""Exercise the installed startup's presentation loop; this test never redraws."""
import ctypes
import json
import os
from pathlib import Path
import runpy
import sys
import time
import bpy

out=Path(sys.argv[sys.argv.index('--')+1])
startup=runpy.run_path(str(Path(__file__).with_name('start_ready.py')))
bpy.context.preferences.view.show_splash=False
user32=ctypes.WinDLL('user32',use_last_error=True)
user32.GetForegroundWindow.restype=ctypes.c_void_p
user32.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
started=time.monotonic()
done=set()
events=[]
def key(vk,label):
    pid=ctypes.c_ulong()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(),ctypes.byref(pid))
    if pid.value!=os.getpid():
        events.append({'action':label,'error':'Not foreground; no key sent'})
        return
    user32.keybd_event(vk,0,0,0)
    def release():
        user32.keybd_event(vk,0,2,0)
    bpy.app.timers.register(release,first_interval=.2)
    events.append({'action':label,'redraws':startup['state']['redraws']})

def tick():
    elapsed=time.monotonic()-started
    for t,vk,label in [(10,0x75,'closed screenshot'),(12,0x24,'open Home'),
                      (16,0x75,'open screenshot'),(19,0x24,'close Home'),
                      (22,0x75,'closed again screenshot')]:
        if elapsed>=t and t not in done:
            key(vk,label)
            done.add(t)
    if elapsed>25:
        (out/'ui.json').write_text(json.dumps({'redraws':startup['state']['redraws'],
            'events':events,'test_called_tag_redraw':False},indent=2))
        bpy.ops.wm.quit_blender()
        return None
    return .25

bpy.app.timers.register(tick,first_interval=1)

