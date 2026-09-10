"""Own factory GUI: NR in actual VIEW_3D, shared settings, folder/export and cleanup."""
import json
from pathlib import Path
import sys
import tempfile
import time
import traceback
import faulthandler
import bpy
import addon_utils

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addon'))
addon_utils.enable('cycles_dlss5', default_set=True, persistent=True)
from cycles_dlss5 import viewport, final_render as final
if '--scene' in sys.argv:
    bpy.ops.wm.open_mainfile(filepath=sys.argv[sys.argv.index('--scene') + 1], load_ui=False, use_scripts=False)
folder = (Path(sys.argv[sys.argv.index('--evidence')+1]) if '--evidence' in sys.argv
          else Path(tempfile.mkdtemp(prefix='dlss5-unified-test-')))
folder.mkdir(parents=True, exist_ok=True)
if '--native' in sys.argv:
    index = sys.argv.index('--native')
    prefs = final.prefs()
    prefs.experimental_native_session = True
    prefs.bridge_path, prefs.runtime_directory = sys.argv[index+1:index+3]
print('UNIFIED_VIEWPORT_EVIDENCE', folder, flush=True)
fault_log = (folder / 'stack.log').open('w')
faulthandler.dump_traceback_later(25, repeat=True, file=fault_log)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 4
scene.cycles.preview_samples = 4
scene.render.resolution_x, scene.render.resolution_y = 128, 96
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.color_depth = '8'
extra_windows = 0
# Old saved settings must not recreate the removed window or BOTH mode.
scene.dlss5_style['display_target'] = 'NEW'
scene.dlss5_style['output_destination'] = 'BOTH'
scene.dlss5_style.intensity = 1.2
bpy.context.preferences.view.show_splash = False
window = bpy.context.window_manager.windows[0]
area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
with bpy.context.temp_override(window=window, area=area):
    area.spaces.active.show_region_ui = True
region = next(r for r in area.regions if r.type == 'WINDOW')
before_windows = len(bpy.context.window_manager.windows)
started = time.monotonic()
stage = 0
first_report = None
second_report = None
first_finished = None
stable_at = None
stable_updates = None
stress_invalidation = False
last_log = 0
original_filepath = bpy.data.filepath


def invoke(name, **kwargs):
    with bpy.context.temp_override(window=window, area=area, region=region):
        return getattr(bpy.ops.cycles_dlss5, name)(**kwargs)


def tick():
    global stage, first_report, second_report, last_log, first_finished, stable_at, stable_updates, stress_invalidation
    try:
        assert bpy.data.filepath == original_filepath
        if time.monotonic() - last_log > 10:
            last_log = time.monotonic()
            s = viewport._session or {}
            print('STAGE', stage, 'revision', s.get('revision'), 'updates', s.get('updates'),
                  'draws', s.get('draws'), 'job', s.get('job') is not None,
                  'status', final.prefs().final_status, flush=True)
        if time.monotonic() - started > 170:
            raise TimeoutError(final.prefs().final_status + ' stage ' + str(stage))
        if stage == 0:
            assert invoke('viewport') == {'FINISHED'}
            assert len(bpy.context.window_manager.windows) == before_windows + extra_windows
            assert viewport._session['scene'] == scene
            assert viewport._session['area'].type == 'VIEW_3D'
            stage = 1
            return .2
        if stage in {1, 2, 25}:
            assert viewport._session is not None, final.prefs().final_status
            session = viewport._session
            if stage == 1 and '--stress' in sys.argv and session['job'] is not None:
                session['revision'] += 1
                stress_invalidation = True
            if session.get('image') is None or session.get('draws', 0) < 1 or session['job'] is not None:
                return .2
            report = json.loads(session['image']['dlss5_report'])
            if '--native' in sys.argv:
                assert report['backend'] == 'experimental-native-display-linear'
                assert report['reset'] is True and report['temporal_accumulation'] is False
            else:
                assert report['nr_confirmed']
            if stage == 1:
                assert session.get('progress') == 100
                if first_finished is None:
                    first_finished = time.monotonic()
                if time.monotonic() - first_finished < 4:
                    return .2
                if stable_at is None:
                    stable_at, stable_updates = time.monotonic(), session['updates']
                    return .2
                if time.monotonic() - stable_at < 5:
                    return .2
                assert session['updates'] == stable_updates, 'Idle NR kept processing new frames'
                first_report = report
                scene.dlss5_style.intensity = .3
                stage = 2
                return .2
            if abs(report['settings']['intensity'] - .3) > .001:
                return .2
            assert report['output_sha256'] != first_report['output_sha256']
            if stage == 2:
                second_report = report
                next(o for o in scene.objects if o.type == 'MESH').location.x += .5
                stage = 25
                return .2
            if report['input_sha256'] == second_report['input_sha256']:
                return .2
            assert len(bpy.context.window_manager.windows) == before_windows + extra_windows
            assert invoke('output_folder', directory=str(folder)) == {'FINISHED'}
            display_before = bpy.context.preferences.view.render_display_type
            assert invoke('final_render') == {'FINISHED'}
            assert bpy.context.preferences.view.render_display_type == display_before
            stage = 3
            return .2
        if final._active is not None or final._pending is not None or final._last_image is None:
            if final.prefs().final_status.startswith(('Ошибка', 'DLSS не запущен')):
                raise RuntimeError(final.prefs().final_status)
            return .2
        assert viewport._session is None, 'File-only render unexpectedly displayed output'
        assert len(bpy.context.window_manager.windows) == before_windows + extra_windows
        assert tuple(final._last_image.size) == (128, 96)
        report = json.loads(final._last_image['dlss5_report'])
        assert abs(report['settings']['intensity'] - .3) < .001
        assert Path(report['saved_path']).parent == folder
        assert Path(report['saved_path']).is_file()
        count = len(bpy.context.window_manager.windows)
        original_matrix = tuple(v for row in area.spaces.active.region_3d.view_matrix for v in row)
        assert invoke('final_show') == {'FINISHED'}
        assert len(bpy.context.window_manager.windows) == count + 1
        from cycles_dlss5 import result_viewer
        assert result_viewer._area.type == 'IMAGE_EDITOR'
        assert result_viewer._area.spaces.active.image == final._last_image
        assert area.type == 'VIEW_3D'
        assert tuple(v for row in area.spaces.active.region_3d.view_matrix for v in row) == original_matrix
        assert viewport._session is None
        assert invoke('final_show') == {'FINISHED'}
        assert len(bpy.context.window_manager.windows) == count + 1
        if '--inspect' not in sys.argv:
            assert invoke('viewport_stop') == {'FINISHED'}
            assert viewport._session is None
        (folder / 'report.json').write_text(json.dumps({'ok': True, 'preview': first_report,
              'final': report, 'same_project': True, 'drawn_in_view3d': True,
              'shared_settings': True, 'scene_edit_refresh': True, 'folder_export': True,
              'notification_stress': stress_invalidation, 'idle_stable': True,
              'image_editor_window': True, 'stage_progress': True}, indent=2))
        print('UNIFIED_VIEWPORT_OK', flush=True)
        faulthandler.cancel_dump_traceback_later()
        if '--inspect' in sys.argv:
            return None
        bpy.ops.wm.quit_blender()
        return None
    except Exception:
        (folder / 'report.json').write_text(json.dumps({'ok': False, 'stage': stage, 'error': traceback.format_exc()}))
        print(traceback.format_exc(), flush=True)
        viewport.stop()
        final.stop_final()
        bpy.ops.wm.quit_blender()
        return None


bpy.app.timers.register(tick, first_interval=3)
