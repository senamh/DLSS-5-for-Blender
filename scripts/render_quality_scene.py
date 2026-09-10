"""Render an untouched official scene camera to SDR PNG in an isolated Blender."""
import json
from pathlib import Path
import sys
import time
import bpy

folder = Path(sys.argv[sys.argv.index('--')+1])
folder.mkdir(parents=True, exist_ok=False)
scene = bpy.context.scene
if hasattr(scene, 'dlss5_style'):
    scene.dlss5_style.final_enabled = False
assert scene.camera is not None
original_size = [scene.render.resolution_x, scene.render.resolution_y]
scale = 1920/max(original_size)
scene.render.resolution_x = round(original_size[0]*scale)
scene.render.resolution_y = round(original_size[1]*scale)
scene.render.resolution_percentage = 100
scene.render.engine = 'CYCLES'
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.cycles.device = 'CPU'
devices = []
try:
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
        if device.use:
            devices.append(device.name)
    if devices:
        scene.cycles.device = 'GPU'
except Exception as error:
    print('GPU fallback:', error, flush=True)
scene.render.image_settings.media_type = 'IMAGE'
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.color_depth = '8'
scene.render.filepath = str(folder/'01-original.png')
scene.render.use_file_extension = True
started = time.monotonic()
bpy.ops.render.render(write_still=True)
report = dict(source=bpy.data.filepath, frame=scene.frame_current,
    camera=scene.camera.name, camera_world=[list(row) for row in scene.camera.matrix_world],
    resolution=[scene.render.resolution_x, scene.render.resolution_y], samples=64,
    denoising=True, devices=devices, render_seconds=time.monotonic()-started,
    compositor=scene.render.use_compositing, view=scene.view_settings.view_transform,
    look=scene.view_settings.look, exposure=scene.view_settings.exposure,
    gamma=scene.view_settings.gamma, blender=bpy.app.version_string)
(folder/'render-settings.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('QUALITY_RENDER_OK', json.dumps(report), flush=True)
