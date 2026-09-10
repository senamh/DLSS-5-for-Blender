"""Real Blender event routing and conflict audit in our own factory window."""
import json
from pathlib import Path
import sys
import tempfile
import traceback
import bpy
import addon_utils

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addon'))
addon_utils.enable('cycles_dlss5', default_set=True)
from cycles_dlss5 import shortcuts, viewport, final_render, output
folder = Path(tempfile.mkdtemp(prefix='dlss5-keyboard-test-'))
print('KEYBOARD_EVIDENCE', folder, flush=True)
window = bpy.context.window_manager.windows[0]
area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
stage = 0
events = []
report = {}
# Isolate keyboard routing from expensive GPU work, tested separately on demos.
original_start, original_stop = viewport.start, viewport.stop
original_draw = output.draw
def start(context, **kwargs):
    events.append('start')
    viewport._session = {'mode': 'PREVIEW', 'job': None}
    return True
def stop(*args, **kwargs):
    events.append('stop')
    viewport._session = None
def draw(layout, scene):
    events.append('render_dialog')
    original_draw(layout, scene)
viewport.start, viewport.stop, output.draw = start, stop, draw

def press(key, ctrl=False, alt=False):
    x, y = region.x + region.width // 2, region.y + region.height // 2
    window.event_simulate(type='MOUSEMOVE', value='NOTHING', x=x, y=y)
    window.event_simulate(type=key, value='PRESS', ctrl=ctrl, alt=alt, x=x, y=y)
    window.event_simulate(type=key, value='RELEASE', ctrl=ctrl, alt=alt, x=x, y=y)

def tick():
    global stage
    try:
        if stage == 0:
            conflicts = []
            for config in (window_manager.keyconfigs.default, window_manager.keyconfigs.user):
                for keymap in config.keymaps:
                    if keymap.name not in {'3D View', '3D View Generic', 'Window', 'Screen', 'Object Mode'}:
                        continue
                    for item in keymap.keymap_items:
                        if (item.active and item.type in {'F6', 'F7', 'F8'}
                            and (item.any or (item.ctrl in {False, -1} and item.alt in {False, -1}
                                             and item.shift in {False, -1} and item.oskey in {False, -1}))
                            and not item.idname.startswith('cycles_dlss5.')):
                            conflicts.append((config.name, keymap.name, item.idname, item.type))
            assert not conflicts, conflicts
            report['default_conflicts'] = conflicts
            assert len(shortcuts._keymaps) == 3
            shortcuts.register()
            assert len(shortcuts._keymaps) == 3
            press('F6')
        elif stage == 1:
            assert events == ['start'], events
            press('F6')
        elif stage == 2:
            assert events == ['start', 'stop'], events
            press('F6')
        elif stage == 3:
            assert events[-1] == 'start', events
            final_render._request = {'test': True}
            press('F8')
        elif stage == 4:
            assert viewport._session is None and final_render._request is None
            assert events[-1] == 'stop'
            report['toggle_and_cancel_events'] = list(events)
            press('F7')
        elif stage == 5:
            assert 'render_dialog' in events, events
            report['render_dialog_invoked'] = True
            press('ESC')  # Dismiss, do not render/write an unrequested test frame.
        elif stage == 6:
            viewport.start, viewport.stop, output.draw = original_start, original_stop, original_draw
            shortcuts.unregister()
            assert not shortcuts._keymaps
            shortcuts.register()
            assert len(shortcuts._keymaps) == 3
            foreign = window_manager.keyconfigs.addon.keymaps.new(name='3D View', space_type='VIEW_3D')
            collision = foreign.keymap_items.new('wm.search_menu', type='F6', value='PRESS')
            try:
                shortcuts.audit()
                assert collision.active
                assert not next(item for _, item in shortcuts._keymaps if item.type == 'F6').active
                assert 'F6' in shortcuts.conflicts
            finally:
                foreign.keymap_items.remove(collision)
            shortcuts.audit()
            assert all(item.active for _, item in shortcuts._keymaps)
            report['foreign_binding_preserved'] = True
            report['ok'] = True
            (folder / 'report.json').write_text(json.dumps(report, indent=2))
            print('KEYBOARD_EVENTS_OK', json.dumps(report), flush=True)
            bpy.ops.wm.quit_blender()
            return None
        stage += 1
        return 1.5
    except Exception:
        viewport._session = None
        viewport.start, viewport.stop, output.draw = original_start, original_stop, original_draw
        report.update(ok=False, stage=stage, error=traceback.format_exc())
        (folder / 'report.json').write_text(json.dumps(report, indent=2))
        print(report['error'], flush=True)
        bpy.ops.wm.quit_blender()
        return None

window_manager = bpy.context.window_manager
bpy.context.preferences.view.show_splash = False
bpy.app.timers.register(tick, first_interval=4)
