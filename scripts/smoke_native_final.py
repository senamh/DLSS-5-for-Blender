"""Background Blender integration: actual Cycles render, native handler, disk output, cancel."""
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch
import bpy
import addon_utils

arguments = sys.argv[sys.argv.index('--')+1:]
addon_parent = Path(arguments[3]) if len(arguments) == 4 else Path(__file__).resolve().parents[1]/'addon'
sys.path.insert(0, str(addon_parent))
addon_utils.enable('cycles_dlss5', default_set=True)
import cycles_dlss5
assert Path(cycles_dlss5.__file__).resolve().parent == (addon_parent/'cycles_dlss5').resolve()
from cycles_dlss5 import final_render as final, output
from cycles_dlss5.styles import values
bridge, runtime, destination = arguments[:3]
out = Path(destination)
out.mkdir(parents=True, exist_ok=False)
p = bpy.context.preferences.addons['cycles_dlss5'].preferences
p.experimental_native_session = True
p.bridge_path, p.runtime_directory = bridge, runtime
# Prove that the experimental path does not resolve the unrelated RenoDX set.
with patch.object(final, 'runtime_paths', side_effect=AssertionError('Wrong backend preflight')):
    final.check_selected_runtime()
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 4
scene.render.resolution_x, scene.render.resolution_y = 128, 96
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.filepath = str(out/'render-')
bpy.ops.cycles_dlss5.style_preset(preset='FILM')
expected = values(scene.dlss5_style)
scene.dlss5_style.final_enabled = True
config = output.snapshot(scene, 'DISK')
final._request = config
before = (scene.render.filepath, scene.view_settings.view_transform, scene.view_settings.exposure)
bpy.ops.render.render()
assert final._pending is not None, p.final_status
scene.dlss5_style.intensity = .2
final.start_pending()
assert final._active is not None, p.final_status
job = final._active['job']
alpha = (job.work/'color.rgba8').read_bytes()[3::4]
assert min(alpha) < 255 and max(alpha) > 0
deadline = time.monotonic()+65
while final._active is not None and time.monotonic() < deadline:
    final.poll_job()
    time.sleep(.05)
assert final._active is None and final._last_image is not None, p.final_status
image = final._last_image
report = json.loads(image['dlss5_report'])
assert report['settings'] == expected
assert report['backend'] == 'experimental-native-display-linear'
assert report['alpha_preserved'] and tuple(image.size) == (128, 96)
assert Path(report['saved_path']).is_file(), p.final_status
assert before == (scene.render.filepath, scene.view_settings.view_transform, scene.view_settings.exposure)
try:
    output.save(image, config)
    raise AssertionError('Overwrite accepted')
except FileExistsError:
    pass
final.begin(scene, values(scene.dlss5_style))
process = final._active['job'].session.process
assert bpy.ops.cycles_dlss5.final_stop() == {'FINISHED'}
assert process.poll() is not None and final._active is None
assert final._last_image == image
(out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
addon_utils.disable('cycles_dlss5', default_set=True)
assert not bpy.app.timers.is_registered(final.poll_job)
print('NATIVE_FINAL_OK: snapshot settings, PNG disk output, alpha, overwrite rejection, cancellation')
