"""Software-OpenGL viewport depth experiment; does not claim NVIDIA execution."""
import bpy, gpu, json, os, sys, time, struct, zlib, subprocess
from pathlib import Path
from mathutils import Vector
import numpy as np
out=Path(sys.argv[sys.argv.index('--')+1]);out.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.preview_samples=4
scene.cycles.use_preview_denoising=False
camera=scene.camera
camera.location=(4,-6,3)
camera.rotation_euler=(Vector((0,0,0))-camera.location).to_track_quat('-Z','Y').to_euler()
window=bpy.context.window
area=next(a for a in window.screen.areas if a.type=='VIEW_3D')
space=area.spaces.active;space.shading.type='RENDERED';space.region_3d.view_perspective='CAMERA'
started=time.monotonic();records=[];captured=set();stage='cycles_overlays_on';requested=False

def capture(phase):
    if not requested or bpy.context.area!=area or (stage,phase) in captured:return
    captured.add((stage,phase))
    item={'stage':stage,'phase':phase,'shading':space.shading.type,'overlays':space.overlay.show_overlays}
    try:
        x,y,w,h=gpu.state.viewport_get()
        item['viewport']=[x,y,w,h]
        values=np.asarray(gpu.state.active_framebuffer_get().read_depth(x,y,w,h)).reshape(h,w).copy()
        np.save(out/(stage+'-'+phase+'.npy'),values)
        color=np.asarray(gpu.state.active_framebuffer_get().read_color(x,y,w,h,4,0,'UBYTE'),dtype=np.uint8).reshape(h,w,4).copy()
        item['color_std']=float(color[:,:,:3].std())
        # Encode framebuffer bytes directly; no image enhancement or display transform.
        def chunk(kind,data):
            return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        rows=b''.join(b'\x00'+row.tobytes() for row in color[::-1])
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',w,h,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')
        (out/(stage+'-'+phase+'-color.png')).write_bytes(png)
        finite=values[np.isfinite(values)]
        item.update(min=float(finite.min()),max=float(finite.max()),std=float(finite.std()),
                    finite_count=int(finite.size),pixel_count=int(values.size),unique=int(np.unique(finite).size))
    except Exception as exc:item['error']=repr(exc)
    records.append(item)

handles=[bpy.types.SpaceView3D.draw_handler_add(capture,(p,),'WINDOW',p) for p in ['POST_VIEW','POST_PIXEL']]
def tick():
    global stage,requested
    elapsed=time.monotonic()-started
    if elapsed>8:requested=True
    if elapsed>13 and stage=='cycles_overlays_on':
        subprocess.run(['import','-window','root',str(out/(stage+'.png'))],check=True,timeout=10)
        stage='cycles_overlays_off';space.overlay.show_overlays=False;requested=False
    if elapsed>18:requested=True
    if elapsed>23 and stage=='cycles_overlays_off':
        subprocess.run(['import','-window','root',str(out/(stage+'.png'))],check=True,timeout=10)
        stage='solid_control';space.shading.type='SOLID';requested=False
    if elapsed>26:requested=True
    area.tag_redraw()
    if elapsed>30:
        result={'blender':bpy.app.version_string,'renderer':gpu.platform.renderer_get(),
            'vendor':gpu.platform.vendor_get(),'nvidia_runtime_tested':False,'records':records}
        (out/'report.json').write_text(json.dumps(result,indent=2))
        for handle in handles:bpy.types.SpaceView3D.draw_handler_remove(handle,'WINDOW')
        bpy.ops.wm.quit_blender();return None
    return .1
bpy.app.timers.register(tick,first_interval=1)

