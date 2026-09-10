"""Exercise Render + DLSS, timer completion, Show and Save through real GUI operators."""
import json
from pathlib import Path
import sys
import tempfile
import time
import traceback
import bpy
import addon_utils

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'addon'))
addon_utils.enable('cycles_dlss5', default_set=True)
from cycles_dlss5 import final_render as final
from cycles_dlss5 import viewport
prefs = bpy.context.preferences.addons['cycles_dlss5'].preferences
prefs.frame_host = sys.argv[sys.argv.index('--') + 1]
prefs.frame_runtime_directory = str(Path(prefs.frame_host).parents[1])
if not (Path(prefs.frame_runtime_directory) / 'nvngx_dlssnr.dll').is_file():
    prefs.frame_runtime_directory = str(Path(bpy.app.binary_path).parent)
folder = Path(tempfile.mkdtemp(prefix='dlss5-render-buttons-test-'))
print('RENDER_BUTTON_TEST_EVIDENCE', folder, flush=True)
window = bpy.context.window_manager.windows[0]
area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
region = next(r for r in area.regions if r.type == 'WINDOW')
scene = window.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 2
scene.render.resolution_x = 128
scene.render.resolution_y = 96
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.filepath = str(folder / 'automatic-')
bpy.ops.cycles_dlss5.style_preset(preset='STRONG')
bpy.context.preferences.view.show_splash = False
started = time.monotonic()
stage = 0
first_input_hash = None
first_output_hash = None
render_count = 0


def counted_render(*_):
    global render_count
    render_count += 1


bpy.app.handlers.render_post.append(counted_render)


def tick():
    global stage, first_input_hash, first_output_hash
    try:
        if time.monotonic() - started > 110:
            raise TimeoutError(prefs.final_status)
        if stage == 0:
            with bpy.context.temp_override(window=window, area=area, region=region):
                assert bpy.ops.cycles_dlss5.final_render() == {'FINISHED'}
            stage = 1
            return .2
        if final._last_image is None or final._active is not None:
            if prefs.final_status.startswith(('Ошибка', 'DLSS не запущен')):
                raise RuntimeError(prefs.final_status)
            return .2
        report = json.loads(final._last_image['dlss5_report'])
        assert tuple(final._last_image.size) == (128, 96)
        if stage == 1:
            assert viewport._session is None
            assert Path(report['saved_path']).is_file()
            assert abs(report['settings']['intensity'] - 1.5) < .001
            first_input_hash = report['input_sha256']
            first_output_hash = report['output_sha256']
            scene.dlss5_style.intensity = .3
            with bpy.context.temp_override(window=window, area=area, region=region):
                assert bpy.ops.cycles_dlss5.final_apply() == {'FINISHED'}
            stage = 2
            return .2
        assert abs(report['settings']['intensity'] - .3) < .001
        from cycles_dlss5 import result_viewer
        assert viewport._session is None, prefs.final_status
        assert result_viewer._area.type == 'IMAGE_EDITOR'
        assert result_viewer._area.spaces.active.image == final._last_image
        assert area.type == 'VIEW_3D'
        assert report['input_sha256'] == first_input_hash, 'Must reprocess original, not accumulate effects'
        assert report['output_sha256'] != first_output_hash, 'Intensity change did not affect output pixels'
        assert render_count == 1, 'Apply should not render the scene again'
        with bpy.context.temp_override(window=window, area=area, region=region):
            before = {w.as_pointer() for w in bpy.context.window_manager.windows}
            assert bpy.ops.cycles_dlss5.final_show() == {'FINISHED'}
            new = [w for w in bpy.context.window_manager.windows if w.as_pointer() not in before]
            assert len(new) == 0, 'Show must reuse the result viewport'
            assert bpy.ops.cycles_dlss5.final_save(filepath=str(folder / 'render.png')) == {'FINISHED'}
        (folder / 'report.json').write_text(json.dumps({'ok': True, 'render_button': True,
            'show_button': True, 'save_button': True, 'apply_without_rerender': True,
            'full_result_in_image_editor': True, 'one_viewer': True, 'nr': report}, indent=2))
        assert (folder / 'render.png').is_file()
        print('RENDER_SHOW_SAVE_BUTTONS_OK', flush=True)
        bpy.ops.wm.quit_blender()
        return None
    except Exception:
        (folder / 'report.json').write_text(json.dumps({'ok': False, 'error': traceback.format_exc()}))
        print(traceback.format_exc(), flush=True)
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=3)
