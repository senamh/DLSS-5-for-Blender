"""Real Blender UI registration test; no native runtime is loaded."""
import json
from pathlib import Path
import sys

import addon_utils
import bpy

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'addon'))


def fail(error):
    raise error


for attempt in range(2):
    module = addon_utils.enable('cycles_dlss5', default_set=True,
                                persistent=True, handle_error=fail)
    assert module is not None
    prefs = bpy.context.preferences.addons['cycles_dlss5'].preferences
    assert prefs.output_order == 'RGB'
    assert not prefs.allow_unrecognized_runtime
    assert not prefs.allow_experimental_color
    prefs.show_advanced = True
    assert prefs.show_advanced
    for cls in module.CLASSES:
        assert cls.is_registered, cls.__name__
    addon_utils.disable('cycles_dlss5', default_set=True, handle_error=fail)
    for cls in module.CLASSES:
        assert not cls.is_registered, cls.__name__
    assert 'cycles_dlss5' not in bpy.context.preferences.addons

output = root / 'dist'
output.mkdir(exist_ok=True)
(output / 'ui-smoke.json').write_text(json.dumps({
    'blender': bpy.app.version_string,
    'registration_reload_preferences': 'passed',
    'native_runtime_executed': False,
}, indent=2), encoding='utf-8')
print('DLSS5_UI_SMOKE_PASSED')

