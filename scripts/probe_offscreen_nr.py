"""Disposable GUI test: can stock Blender expose clean rendered viewport pixels?"""
from pathlib import Path
import tempfile
import traceback
import runpy
import bpy
import gpu
import numpy as np

folder = Path(tempfile.mkdtemp(prefix='dlss5-offscreen-'))
window = bpy.context.window_manager.windows[0]
area = next(a for a in window.screen.areas if a.type == 'VIEW_3D')
area.spaces.active.shading.type = 'RENDERED'
bpy.context.scene.render.engine = 'CYCLES'
bpy.context.scene.cycles.device = 'CPU'
bpy.context.scene.cycles.preview_samples = 4
state = {'ready': False, 'busy': False, 'done': False}


def draw():
    if not state['ready'] or state['busy'] or state['done'] or bpy.context.area != area:
        return
    state['busy'] = True
    offscreen = None
    try:
        offscreen = gpu.types.GPUOffScreen(256, 192)
        view = area.spaces.active.region_3d
        offscreen.draw_view3d(window.scene, window.view_layer, area.spaces.active,
                             bpy.context.region, view.view_matrix, view.window_matrix,
                             do_color_management=True, draw_background=True)
        with offscreen.bind():
            pixels = gpu.state.active_framebuffer_get().read_color(0, 0, 256, 192, 4, 0, 'UBYTE')
            pixels.dimensions = 256 * 192 * 4
            array = np.array(pixels, dtype=np.uint8).reshape(192, 256, 4)
        np.save(folder / 'pixels.npy', array)
        write_png = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'addon/cycles_dlss5/frame_result.py'))['write_rgba_png']
        write_png(folder / 'viewport.png', array[::-1].tobytes(), 256, 192)
        print('OFFSCREEN_PROBE', folder, float(array[:, :, :3].mean()), float(array[:, :, :3].std()), flush=True)
    except Exception:
        print(traceback.format_exc(), flush=True)
    finally:
        if offscreen is not None:
            offscreen.free()
        state['done'] = True
        state['busy'] = False


handle = bpy.types.SpaceView3D.draw_handler_add(draw, (), 'WINDOW', 'POST_PIXEL')


def tick():
    if state['done']:
        bpy.types.SpaceView3D.draw_handler_remove(handle, 'WINDOW')
        bpy.ops.wm.quit_blender()
        return None
    state['ready'] = True
    area.tag_redraw()
    return 1


bpy.app.timers.register(tick, first_interval=6)
