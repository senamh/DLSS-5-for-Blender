"""Run inside the built Blender; tests registration/reload, not neural rendering."""
import importlib.util
import json
from pathlib import Path

import addon_utils
import bpy
import _cycles

root = Path(bpy.app.binary_path).parent
assert _cycles.with_dlss5nr, 'Compiled DLSS backend is missing'
spec = importlib.util.spec_from_file_location('portable_start', root / 'start_portable.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)
for attempt in range(2):
    module = launcher.enable_ui()
    assert addon_utils.check('cycles_dlss5')[1], 'UI enable failed'
    assert 'cycles_dlss5' in bpy.context.preferences.addons
    for cls in module.CLASSES:
        assert cls.is_registered, f'{cls.__name__} was not registered'
    addon_utils.disable('cycles_dlss5', default_set=True)
    for cls in module.CLASSES:
        assert not cls.is_registered, f'{cls.__name__} leaked on disable'
launcher.enable_ui()
(root / 'blender-smoke.json').write_text(json.dumps({
    'blender_version': bpy.app.version_string,
    'backend_import': True,
    'addon_enable_disable_reload': True,
    'neural_rendering_tested': False,
}, indent=2), encoding='utf-8')
print('Portable UI registration and reload passed; neural rendering NOT tested.')

