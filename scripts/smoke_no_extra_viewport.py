"""The removed additional-window feature must not be registered."""
from pathlib import Path
import sys
import bpy
import addon_utils

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addon'))
addon_utils.enable('cycles_dlss5', default_set=True)
assert not hasattr(bpy.types, 'CYCLES_DLSS5_OT_open_preview')
assert not hasattr(bpy.context.scene.dlss5_style, 'display_target')
assert not hasattr(bpy.context.scene.dlss5_style, 'output_destination')
print('NO_ADDITIONAL_VIEWPORT_OK')
