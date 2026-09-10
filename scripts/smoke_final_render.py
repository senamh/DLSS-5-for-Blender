"""Real render + NR + settings/alpha/save/cancel checks in factory background Blender."""
import json
from pathlib import Path
import sys
import tempfile
import time
import bpy
import addon_utils

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'addon'))
addon_utils.enable('cycles_dlss5', default_set=True)
from cycles_dlss5 import final_render as final
from cycles_dlss5.styles import values
out = Path(tempfile.mkdtemp(prefix='dlss5-final-test-'))
print('FINAL_TEST_EVIDENCE', out, flush=True)
prefs = bpy.context.preferences.addons['cycles_dlss5'].preferences
prefs.frame_host = sys.argv[sys.argv.index('--') + 1]
prefs.frame_runtime_directory = str(Path(prefs.frame_host).parents[1])
if not (Path(prefs.frame_runtime_directory) / 'nvngx_dlssnr.dll').is_file():
    prefs.frame_runtime_directory = str(Path(bpy.app.binary_path).parent)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 4
scene.render.resolution_x = 128
scene.render.resolution_y = 96
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.view_settings.exposure = .5
scene.render.filepath = 'preserve-this-output-path'
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
bpy.ops.cycles_dlss5.style_preset(preset='FILM')
expected = values(scene.dlss5_style)


def state():
    return (scene.render.filepath, scene.render.resolution_x, scene.render.resolution_y,
            scene.render.image_settings.file_format, scene.render.image_settings.color_mode,
            scene.render.image_settings.color_depth, scene.view_settings.exposure,
            scene.cycles.samples, scene.use_nodes, bpy.data.filepath)


before = state()
bpy.ops.render.render()
assert final._pending is not None, 'F12-equivalent handler did not run'
scene.dlss5_style.intensity = .2  # In-flight settings must not change.
final.start_pending()
assert final._active is not None, prefs.final_status
job = final._active['job']
alpha = (job.work / 'color.rgba8').read_bytes()[3::4]
assert min(alpha) < 255 and max(alpha) > 0, 'Transparency fixture is not meaningful'
ini = (job.root / 'ReShade.ini').read_text()
assert 'NRIntensity=1.150000' in ini
assert 'NRLocalTone=1.150000' in ini
assert 'NRLocalStructure=1.100000' in ini
assert 'NRSkinStructure=0.750000' in ini
assert 'NRAutoMask=1' in ini
assert 'NRStyle=0' in ini
deadline = time.monotonic() + 65
while final._active is not None and time.monotonic() < deadline:
    final.poll_job()
    time.sleep(.1)
assert final._last_image is not None, prefs.final_status
image = final._last_image
report = json.loads(image['dlss5_report'])
assert report['nr_confirmed'] and report['settings'] == expected
assert report['alpha_preserved']
assert tuple(image.size) == (128, 96)
assert state() == before, (state(), before)
assert image.use_view_as_render is False
assert bpy.data.images.get('Render Result') is not None
assert bpy.ops.cycles_dlss5.final_save(filepath=str(out / 'final.png')) == {'FINISHED'}
assert (out / 'final.png').is_file()
try:
    result = bpy.ops.cycles_dlss5.final_save(filepath=str(out / 'final.png'))
except RuntimeError:
    result = {'CANCELLED'}
assert result == {'CANCELLED'}, 'Must not silently overwrite a file'
final.begin(scene, values(scene.dlss5_style))
process = final._active['job'].process
assert bpy.ops.cycles_dlss5.final_stop() == {'FINISHED'}
assert final._active is None and process.poll() is not None
assert final._last_image == image, 'Cancel destroyed previous good result'
(out / 'report.json').write_text(json.dumps(report, indent=2))
print('FINAL_RENDER_TEST_OK', json.dumps(report), flush=True)
addon_utils.disable('cycles_dlss5', default_set=True)
