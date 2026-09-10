"""Exercise actual modal render and viewport operators in a disposable UI window."""
import json
import os
from pathlib import Path
import sys
import time
import traceback

import numpy as np
import addon_utils
import bpy
bpy.context.preferences.view.show_splash = False

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'addon'))
addon_utils.enable('cycles_dlss5', default_set=True, persistent=False)
from cycles_dlss5 import stock

key = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
workspace = Path(os.environ['RUNNER_TEMP']) / ('dlss5-' + key)
output = root/'gpu-results'/'stock-ui'
output.mkdir(parents=True, exist_ok=False)
os.environ['CYCLES_DLSS5_CAPTURE_EVIDENCE'] = str(output/'raw-frames')
prefs = bpy.context.preferences.addons['cycles_dlss5'].preferences
prefs.runtime_directory = str(workspace/'runtime')
prefs.bridge_path = str(workspace/'dlss5nr_bridge.dll')
prefs.probe_report = str(root/'gpu-results'/key/'report.json')
prefs.allow_unrecognized_runtime = True
prefs.allow_experimental_color = True
prefs.preview_auto = True

sys.path.insert(0, str(root/'scripts'))
from stock_test_scene import setup
setup()

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 8
scene.cycles.preview_samples = 8
scene.render.resolution_x = 256
scene.render.resolution_y = 256
scene.render.resolution_percentage = 100
view = next(a for a in bpy.context.screen.areas if a.type == 'VIEW_3D')
editor = next(a for a in bpy.context.screen.areas if a.type == 'PROPERTIES')
started = time.monotonic()
phase = 'render'
report = {'passed': False, 'blender': bpy.app.version_string}
samples = []
worker_pids = set()


def invoke_view(**kwargs):
    region = next(r for r in view.regions if r.type == 'WINDOW')
    with bpy.context.temp_override(window=bpy.context.window, area=view, region=region):
        return bpy.ops.cycles_dlss5.stock(**kwargs)


def finish(error=None):
    if error:
        report['error'] = error
    stock.stop_stock()
    report['elapsed_seconds'] = time.monotonic()-started
    (output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('STOCK_UI_RESULT', json.dumps(report), flush=True)
    bpy.ops.wm.quit_blender()
    return None


def tick():
    global phase
    try:
        if time.monotonic()-started > 180:
            return finish('UI test timed out in phase '+phase)
        if phase == 'render':
            bpy.ops.render.render()
            assert invoke_view(viewport=False) == {'RUNNING_MODAL'}
            phase = 'render_wait'
        elif phase == 'render_wait':
            image = bpy.data.images.get('DLSS Render')
            if image is None:
                if stock._active is None:
                    return finish('Render operator exited without an output image')
                return .5
            report['render_operator'] = 'passed'
            view.spaces.active.shading.type = 'RENDERED'
            view.spaces.active.overlay.show_overlays = False
            phase = 'preview_start'
            return 3.0
        elif phase == 'preview_start':
            assert invoke_view(viewport=True) == {'RUNNING_MODAL'}
            phase = 'preview_wait'
        elif phase == 'preview_wait':
            image = bpy.data.images.get('DLSS Viewport Preview')
            updates = int(image.get('dlss_updates', 0)) if image else 0
            if updates > len(samples):
                samples.append(float(image['dlss_worker_seconds']))
                worker_pids.add(int(image['dlss_worker_pid']))
            if updates >= 1 and not report.get('scene_changed'):
                scene.world.color = (.4, .03, .01)
                bpy.data.objects['Cube'].rotation_euler.z += .6
                view.tag_redraw()
                report['scene_changed'] = True
                report['changed_at_update'] = updates
            if updates >= 40 and updates >= report.get('changed_at_update', updates)+2:
                assert image.get('dlss_viewport_draws', 0) >= 2, 'No direct viewport drawing'
                report['direct_viewport_draws'] = image['dlss_viewport_draws']
                assert not any(a.type == 'IMAGE_EDITOR' for a in bpy.context.screen.areas)
                report['without_image_editor'] = True
                bpy.ops.screen.screenshot(filepath=str(output/'viewport.png'))
                assert len(worker_pids) == 1, 'Preview worker was restarted'
                report['preview_updates'] = updates
                report['frame_seconds'] = samples
                report['persistent_worker'] = True
                report['last_worker_seconds'] = image['dlss_worker_seconds']
                report['preview_size'] = list(image.size)
                report['comparison_mode'] = prefs.preview_compare
                report['mean_pixel_change'] = image['dlss_mean_change']
                raw = np.load(output/'raw-frames'/'input-1.npy', allow_pickle=False)
                report['captured_nonblack_fraction'] = float(np.mean(np.max(raw[:, :, :3], axis=2) > .01))
                assert report['captured_nonblack_fraction'] > .25, 'Captured overlay instead of the known lit scene'
                assert np.all(raw[:, :, 3] == 1), 'Viewport output would be transparent'
                later = np.load(output/'raw-frames'/'input-40.npy', allow_pickle=False)
                drift = float(np.mean(np.abs(later-raw)))
                report['capture_drift'] = drift
                assert 1e-5 < drift < .08, 'Capture is static or accumulating its own output'
                image.filepath_raw = str(output/'preview.exr')
                image.file_format = 'OPEN_EXR'
                image.save()
                prefs.preview_auto = False
                phase = 'manual_idle'
                return .5
            if stock._active is None:
                return finish('Preview operator exited before two updates')
        elif phase == 'manual_idle':
            if stock._active._inflight:
                return .2
            report['manual_baseline'] = bpy.data.images['DLSS Viewport Preview']['dlss_updates']
            phase = 'manual_check'
            return 1.0
        elif phase == 'manual_check':
            assert bpy.data.images['DLSS Viewport Preview']['dlss_updates'] == report['manual_baseline'], 'Manual preview keeps capturing'
            assert invoke_view(viewport=True) == {'FINISHED'}
            phase = 'manual_refresh'
        elif phase == 'manual_refresh':
            if bpy.data.images['DLSS Viewport Preview']['dlss_updates'] <= report['manual_baseline']:
                return .2
            report['manual_preview'] = 'stable until explicit refresh'
            bpy.ops.cycles_dlss5.stock_stop()
            assert stock._active is None
            report['stop_operator'] = 'passed'
            report['passed'] = True
            return finish()
        return .5
    except Exception:
        return finish(traceback.format_exc())


bpy.app.timers.register(tick, first_interval=2.0)

