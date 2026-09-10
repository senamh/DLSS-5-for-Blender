"""Check the updated installed extension, empty-preference runtime discovery and one UI."""
from pathlib import Path
import sys
import bpy
import addon_utils

extension = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
sys.path.insert(0, str(extension.parent))
addon_utils.enable('cycles_dlss5', default_set=True)
import cycles_dlss5
assert Path(cycles_dlss5.__file__).resolve().parent == extension
assert cycles_dlss5.bl_info['version'] == (0, 2, 2)
from cycles_dlss5.final_render import runtime_paths, HANDLERS
host, runtime = runtime_paths()
assert host.is_file() and host.parent == runtime / 'frame-host'
assert not hasattr(bpy.types, 'CYCLES_DLSS5_PT_render')
assert not hasattr(bpy.types, 'CYCLES_DLSS5_PT_stock_view')
assert bpy.types.CYCLES_DLSS5_PT_preview_launcher.is_registered
assert all(collection.count(callback) == 1 for collection, callback in HANDLERS)
assert not hasattr(bpy.types, 'CYCLES_DLSS5_OT_open_preview')
print('INSTALLED_022_OK', host)
addon_utils.disable('cycles_dlss5', default_set=True)
