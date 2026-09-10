"""Registration-only test in Blender; does not start a native host or render."""
from pathlib import Path
import sys
import bpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addon'))
import cycles_dlss5

for _ in range(2):
    cycles_dlss5.register()
    assert hasattr(bpy.types, 'CYCLES_DLSS5_OT_frame')
    assert 'filepath' in bpy.ops.cycles_dlss5.frame.get_rna_type().properties
    assert bpy.ops.cycles_dlss5.style_preset(preset='FILM') == {'FINISHED'}
    assert abs(bpy.context.scene.dlss5_style.intensity - 1.15) < .0001
    assert bpy.context.scene.dlss5_style.style == '0'
    cycles_dlss5.unregister()
    assert not hasattr(bpy.types, 'CYCLES_DLSS5_OT_frame')
    assert not hasattr(bpy.types.Scene, 'dlss5_style')
print('FRAME_ADDON_REGISTRATION_OK')
