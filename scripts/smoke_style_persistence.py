"""Check actual Blender .blend persistence and both UI draw functions without GPU."""
from pathlib import Path
import sys
import tempfile
import bpy
import addon_utils

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addon'))
addon_utils.enable('cycles_dlss5', default_set=True)
from cycles_dlss5.styles import values, draw_styles
from cycles_dlss5.preview_launch import draw_preview
from cycles_dlss5.viewport import scene_changed

bpy.ops.cycles_dlss5.style_preset(preset='FILM')
bpy.context.scene.dlss5_style.tone = .42
bpy.context.scene.dlss5_style.auto_mask = False
expected = values(bpy.context.scene.dlss5_style)
with tempfile.TemporaryDirectory(prefix='dlss5-style-save-test-') as folder:
    path = str(Path(folder) / 'styles.blend')
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
    bpy.context.scene.dlss5_style.tone = 1.9
    bpy.ops.wm.open_mainfile(filepath=path, load_ui=False, use_scripts=False)
    assert values(bpy.context.scene.dlss5_style) == expected
    assert bpy.app.handlers.depsgraph_update_post.count(scene_changed) == 1

class Layout:
    operators = []
    properties = []

    def operator(self, name, **kwargs):
        self.operators.append(name)
        return Layout()

    def prop(self, obj, name, **kwargs):
        self.properties.append(name)

    def __getattr__(self, name):
        return lambda *args, **kwargs: Layout()

prefs = bpy.context.preferences.addons['cycles_dlss5'].preferences
prefs.show_advanced = False
draw_preview(Layout(), prefs, bpy.context)
assert Layout.operators == ['cycles_dlss5.viewport', 'cycles_dlss5.final_render'], Layout.operators
assert Layout.properties == ['intensity', 'show_advanced'], Layout.properties
prefs.show_advanced = True
draw_preview(Layout(), prefs, bpy.context)
assert 'cycles_dlss5.open_preview' not in Layout.operators
assert 'cycles_dlss5.style_preset' in Layout.operators
print('STYLE_PERSISTENCE_AND_DRAW_OK', expected)
