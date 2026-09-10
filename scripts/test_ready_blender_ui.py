"""Exercise factory Blender; all image processing belongs to upstream ReShade addons."""
import json
from pathlib import Path
import sys
import time
import bpy
import gpu

output = Path(sys.argv[sys.argv.index('--')+1])
bpy.context.preferences.view.show_splash = False
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.preview_samples = 16
scene.cycles.use_preview_denoising = True
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for device in prefs.devices:
    device.use = device.type == 'OPTIX'
scene.cycles.device = 'GPU' if any(d.use for d in prefs.devices) else 'CPU'
area = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
area.spaces.active.shading.type = 'RENDERED'
started = time.monotonic()
ticks = 0

def tick():
    global ticks
    ticks += 1
    if ticks % 12 == 0:
        bpy.data.objects['Cube'].rotation_euler.z += .08
    area.tag_redraw()
    if time.monotonic()-started > 50:
        (output/'blender.json').write_text(json.dumps(dict(blender=bpy.app.version_string,
            backend=gpu.platform.backend_type_get(), cycles_device=scene.cycles.device,
            ticks=ticks, custom_addon_loaded='cycles_dlss5' in bpy.context.preferences.addons)))
        bpy.ops.screen.screenshot(filepath=str(output/'blender.png'))
        bpy.ops.wm.quit_blender()
        return None
    return .5

bpy.app.timers.register(tick,first_interval=2)

