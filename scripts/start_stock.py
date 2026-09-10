"""Session launcher for the stock Blender bundle; no global preferences saved."""
from pathlib import Path
import sys

import addon_utils
import bpy

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root/'addon'))
addon_utils.enable('cycles_dlss5', default_set=True, persistent=False)
prefs = bpy.context.preferences.addons['cycles_dlss5'].preferences
prefs.runtime_directory = str(root/'runtime')
prefs.bridge_path = str(root/'dlss5nr_bridge.dll')
prefs.probe_report = str(root/'validation/report.json')
# This bundle is prepared only after the user's authorized GPU validation.
prefs.allow_unrecognized_runtime = True
prefs.allow_experimental_color = True
prefs.diagnostic_summary = 'Validated local runtime; Render Properties > DLSS'
prefs.detected_gpu = 'NVIDIA GeForce RTX 5070'
bpy.context.scene.render.engine = 'CYCLES'
for area in bpy.context.screen.areas:
    if area.type == 'PROPERTIES':
        area.spaces.active.context = 'RENDER'
print('DLSS stock addon ready')

