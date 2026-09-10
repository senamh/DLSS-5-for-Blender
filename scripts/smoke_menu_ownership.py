"""Real Blender registration ownership, menu inventory and handler lifecycle checks."""
import importlib.util
from pathlib import Path
import sys
import types
import bpy

root = Path(__file__).resolve().parents[1] / 'addon/cycles_dlss5'
sys.path.insert(0, str(root.parent))
import cycles_dlss5 as first
first.register()
first.register()  # Repeated registration must not append panels or handlers.
assert not hasattr(bpy.types, 'CYCLES_DLSS5_PT_render')
assert not hasattr(bpy.types, 'CYCLES_DLSS5_PT_stock_view')
parent = types.ModuleType('test_extension')
parent.__path__ = []
sys.modules[parent.__name__] = parent
spec = importlib.util.spec_from_file_location('test_extension.cycles_dlss5', root / '__init__.py',
                                            submodule_search_locations=[str(root)])
second = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = second
spec.loader.exec_module(second)
second.register()
assert bpy._cycles_dlss5_owner is second
assert not first.shortcuts._keymaps
if bpy.context.window_manager.keyconfigs.addon is not None:
    assert len(second.shortcuts._keymaps) == 3
first.unregister()  # Disabling the old owner must not unregister the new owner.
assert bpy.types.CYCLES_DLSS5_PT_preview_launcher.is_registered
from test_extension.cycles_dlss5 import final_render
for collection, callback in final_render.HANDLERS:
    assert collection.count(callback) == 1
    assert not any(getattr(f, '__module__', '') == 'cycles_dlss5.final_render' for f in collection)
for preset in ('SOFT', 'BALANCED', 'FILM', 'STRONG'):
    assert bpy.ops.cycles_dlss5.style_preset(preset=preset) == {'FINISHED'}
second.unregister()
assert not second.shortcuts._keymaps
for collection, callback in final_render.HANDLERS:
    assert callback not in collection
assert not hasattr(bpy.types, 'CYCLES_DLSS5_PT_preview_launcher')
print('SINGLE_MENU_AND_HANDLERS_OK')
