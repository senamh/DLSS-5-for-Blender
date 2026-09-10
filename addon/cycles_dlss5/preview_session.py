"""Bootstrap a scene copy in the installed preview, without loading saved UI/scripts."""
from pathlib import Path
import runpy
import sys
import bpy
import addon_utils
import json


def main():
    snapshot, addon, scene_name = sys.argv[sys.argv.index('--') + 1:][:3]
    bpy.context.preferences.filepaths.use_load_ui = False
    bpy.ops.wm.open_mainfile(filepath=snapshot, load_ui=False, use_scripts=False)
    window = next(w for w in bpy.context.window_manager.windows if w.screen)
    if scene_name in bpy.data.scenes:
        window.scene = bpy.data.scenes[scene_name]
    sys.path.insert(0, str(Path(addon).parent))
    with bpy.context.temp_override(window=window):
        addon_utils.enable(Path(addon).name, default_set=True)
        from cycles_dlss5.styles import values
        print('DLSS5_SESSION_STYLE ' + json.dumps(values(window.scene.dlss5_style)), flush=True)
        runpy.run_path(str(Path(bpy.app.binary_path).with_name('start_preview.py')))
        # The launcher supplies its operator; the addon supplies the complete UI.
        # Avoid two competing preview panels in the same sidebar tab.
        legacy_panel = getattr(bpy.types, 'DLSS5_PT_preview', None)
        if legacy_panel is not None:
            bpy.utils.unregister_class(legacy_panel)
        area = next((a for a in window.screen.areas if a.type == 'VIEW_3D'), None)
        if area:
            area.spaces.active.show_region_ui = True
            if window.scene.camera:
                area.spaces.active.region_3d.view_perspective = 'CAMERA'


if __name__ == '__main__':
    main()
