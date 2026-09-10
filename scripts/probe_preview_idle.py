"""Official scene: record why a supposedly idle preview invalidates its result."""
import json
from pathlib import Path
import sys
import tempfile
import time
import bpy
import addon_utils

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addon'))
addon_utils.enable('cycles_dlss5', default_set=True, persistent=True)
from cycles_dlss5 import viewport, final_render
bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index('--') + 1], load_ui=False, use_scripts=False)
scene = bpy.context.scene
scene.cycles.preview_samples = 4
scene.cycles.device = 'CPU'
window = bpy.context.window_manager.windows[0]
area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
events = []
started = time.monotonic()
folder = Path(tempfile.mkdtemp(prefix='dlss5-idle-probe-'))
print('IDLE_PROBE', folder, flush=True)
previous = None
def updates(scene, graph):
    if viewport._session and not viewport._session.get('capturing'):
        events.append({'at': round(time.monotonic()-started, 2), 'depsgraph':
            [(u.id.name, type(u.id).__name__, u.is_updated_transform, u.is_updated_geometry, u.is_updated_shading)
             for u in graph.updates][:30]})
bpy.app.handlers.depsgraph_update_post.append(updates)
def tick():
    global previous
    elapsed = time.monotonic() - started
    if previous is None:
        with bpy.context.temp_override(window=window, area=area, region=region):
            viewport.start(bpy.context)
        previous = viewport.key(viewport._session)
    session = viewport._session
    if session:
        current = viewport.key(session)
        if current != previous:
            events.append({'at': round(elapsed,2), 'key_fields': [i for i,(a,b) in enumerate(zip(previous,current)) if a != b]})
            previous = current
    if elapsed > 35 or session is None:
        result = dict(updates=(session or {}).get('updates'), draws=(session or {}).get('draws'),
                      revision=(session or {}).get('revision'), status=final_render.prefs().final_status, events=events)
        (folder/'report.json').write_text(json.dumps(result, indent=2))
        print('IDLE_PROBE_RESULT', json.dumps(result), flush=True)
        viewport.stop()
        bpy.ops.wm.quit_blender()
        return None
    return .2
bpy.app.timers.register(tick, first_interval=3)
