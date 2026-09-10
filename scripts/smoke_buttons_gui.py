"""Test actual registered buttons against the installed native preview in a test window."""
import json
from pathlib import Path
import runpy
import sys
import time
import traceback
import bpy
import addon_utils

root = Path(__file__).resolve().parents[1]
folder = Path(sys.argv[sys.argv.index('--') + 1])
sys.path.insert(0, str(root / 'addon'))
addon_utils.enable('cycles_dlss5', default_set=True)
bootstrap = runpy.run_path(str(root / 'scripts/start_preview.py'))
window = bpy.context.window_manager.windows[0]
window.scene.name = 'DLSS BUTTON TEST'
window.scene.dlss5_style.final_enabled = False
area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
area.spaces.active.show_region_ui = True
started = time.monotonic()
stage = 0
report = {}


def press(action):
    with bpy.context.temp_override(window=window, area=area, region=region):
        result = bpy.ops.dlss5.control(action=action)
    assert result == {'FINISHED'}, (action, result)


def enabled():
    preset = (folder / 'ReShadePreset.ini').read_text()
    return 'DLSS5_Feed@DLSS5_Feed.fx' in next(line for line in preset.splitlines() if line.startswith('Techniques='))


def compilations():
    return (folder / 'ReShade.log').read_text(errors='replace').count('Successfully compiled')


def tick():
    global stage
    try:
        elapsed = time.monotonic() - started
        if stage == 0 and elapsed > 12:
            report['native_panel_count'] = int(hasattr(bpy.types, 'DLSS5_PT_preview'))
            report['addon_panel'] = hasattr(bpy.types, 'CYCLES_DLSS5_PT_preview_launcher')
            assert not report['native_panel_count'] and report['addon_panel']
            assert bootstrap['send_key'](121)  # Physical F10 equivalent must no longer toggle DLSS.
            stage = 1
        elif stage == 1 and elapsed > 17:
            report['f10_no_effect'] = enabled()
            assert report['f10_no_effect']
            press('TOGGLE')
            stage = 2
        elif stage == 2 and elapsed > 22:
            report['toggle_off'] = not enabled()
            assert report['toggle_off']
            press('TOGGLE')
            stage = 3
        elif stage == 3 and elapsed > 27:
            report['toggle_on'] = enabled()
            assert report['toggle_on']
            report['compiles_before'] = compilations()
            assert bootstrap['send_key'](117)
            assert bootstrap['send_key'](118)
            stage = 4
        elif stage == 4 and elapsed > 32:
            report['f6_no_screenshot'] = not any((folder / 'Screenshots').glob('*.png'))
            report['f7_no_reload'] = compilations() == report['compiles_before']
            assert report['f6_no_screenshot'] and report['f7_no_reload']
            press('RELOAD')
            stage = 5
        elif stage == 5 and elapsed > 41:
            report['reload_confirmed'] = compilations() > report['compiles_before']
            assert report['reload_confirmed']
            press('SCREENSHOT')
            stage = 6
        elif stage == 6 and elapsed > 47:
            report['screenshot_created'] = any((folder / 'Screenshots').glob('*.png'))
            assert report['screenshot_created']
            press('OVERLAY')
            report['overlay_open_dispatched'] = True
            stage = 7
        elif stage == 7 and elapsed > 64:
            press('OVERLAY')
            report['overlay_close_dispatched'] = True
            stage = 8
        elif stage == 8 and elapsed > 90:
            report['nr_confirmed'] = 'inline feature 18 evaluation succeeded' in (folder / 'ReShade.log').read_text(errors='replace')
            (folder / 'buttons.json').write_text(json.dumps(report, indent=2))
            print('BUTTON_TEST_RESULT', json.dumps(report), flush=True)
            bpy.ops.wm.quit_blender()
            return None
        (folder / 'progress.json').write_text(json.dumps({'stage': stage, **report}, indent=2))
        return .5
    except Exception:
        (folder / 'buttons.json').write_text(json.dumps({'error': traceback.format_exc(), **report}, indent=2))
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=1)
