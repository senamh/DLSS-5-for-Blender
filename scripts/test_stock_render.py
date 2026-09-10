"""Run inside official Blender: real Cycles render -> stock addon -> native worker."""
import json
import os
from pathlib import Path
import subprocess
import sys

import bpy
import numpy as np

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'addon'))
from cycles_dlss5.stock import CYCLES_DLSS5_OT_stock

workspace = Path(os.environ['RUNNER_TEMP']) / ('dlss5-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'])
output = root / 'gpu-results' / 'stock-render'
output.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(root/'scripts'))
from stock_test_scene import setup
setup()

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 8
scene.render.resolution_x = 256
scene.render.resolution_y = 256
scene.render.resolution_percentage = 100
scene.render.film_transparent = True
bpy.ops.render.render()

class Capture:
    _root = output

    def launch(self, frame):
        self.frame = frame

capture = Capture()
previous = (scene.render.image_settings.file_format, scene.render.image_settings.color_mode,
            scene.render.image_settings.color_depth)
CYCLES_DLSS5_OT_stock.read_render(capture, bpy.context)
assert previous == (scene.render.image_settings.file_format, scene.render.image_settings.color_mode,
                    scene.render.image_settings.color_depth)
assert capture.frame.shape == (256, 256, 4)
np.save(output/'input.npy', capture.frame)
job = dict(runtime=str(workspace/'runtime'), bridge=str(workspace/'dlss5nr_bridge.dll'),
           order='RGB', input=str(output/'input.npy'), output=str(output/'output.npy'))
(output/'job.json').write_text(json.dumps(job), encoding='utf-8')
with (output/'worker.log').open('w', encoding='utf-8') as log:
    result = subprocess.run([bpy.app.binary_path, '--background', '--factory-startup',
                             '--python-exit-code', '1', '--python',
                             str(root/'addon/cycles_dlss5/stock_worker.py'), '--', str(output/'job.json')],
                            stdout=log, stderr=subprocess.STDOUT, timeout=120)
if result.returncode:
    raise RuntimeError((output/'worker.log').read_text(encoding='utf-8', errors='replace')[-3000:])
frame = np.load(output/'output.npy', allow_pickle=False)
assert frame.shape == capture.frame.shape and np.isfinite(frame).all()
assert np.array_equal(frame[:, :, 3], capture.frame[:, :, 3])
change = float(np.mean(np.abs(frame[:, :, :3]-capture.frame[:, :, :3])))
assert change > 1e-5, 'Neural image change unconfirmed'
image = bpy.data.images.new('DLSS Stock Test', width=256, height=256, alpha=True, float_buffer=True)
image.pixels.foreach_set(frame.ravel())
image.filepath_raw = str(output/'dlss.exr')
image.file_format = 'OPEN_EXR'
image.save()
(output/'report.json').write_text(json.dumps(dict(passed=True, blender=bpy.app.version_string,
    mean_absolute_change=change, alpha_preserved=True, viewport_tested=False)), encoding='utf-8')
print('STOCK_RENDER_TEST_PASSED', change)

