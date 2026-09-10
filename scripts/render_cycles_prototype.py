"""Export a bounded Cycles test render without changing the original .blend."""
import json
from pathlib import Path
import sys

import bpy
sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_cycles_guides import export_guides

config = json.loads(Path(sys.argv[sys.argv.index('--') + 1]).read_text())
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = config.get('samples', 8)
scene.cycles.device = 'CPU'
scene.render.resolution_percentage = max(1, min(100, int(
    config.get('long_side', 512) * 100 /
    max(scene.render.resolution_x, scene.render.resolution_y))))
meta = export_guides(scene, config['export'])
print('CYCLES_GUIDES_EXPORTED', json.dumps(meta), flush=True)
