"""Test the unchanged upstream stack; capture through ReShade, not Blender's framebuffer."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time
import bpy
from mathutils import Vector

out = Path(sys.argv[sys.argv.index('--')+1])
assets = out/'assets'
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(assets/'LeePerrySmith.glb'))
meshes = [o for o in bpy.context.scene.objects if o.type=='MESH']
material=bpy.data.materials.new('Scan texture')
material.use_nodes=True
shader=material.node_tree.nodes.get('Principled BSDF')
shader.inputs['Roughness'].default_value=.5
texture=material.node_tree.nodes.new('ShaderNodeTexImage')
texture.image=bpy.data.images.load(str(assets/'Map-COL.jpg'))
material.node_tree.links.new(texture.outputs['Color'],shader.inputs['Base Color'])
for obj in meshes:
    obj.data.materials.clear()
    obj.data.materials.append(material)
    for poly in obj.data.polygons:
        poly.use_smooth=True
bpy.context.view_layer.update()
points=[o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
low=Vector(tuple(min(p[i] for p in points) for i in range(3)))
high=Vector(tuple(max(p[i] for p in points) for i in range(3)))
center=(low+high)/2
height=high.z-low.z
scene=bpy.context.scene
camera=bpy.data.objects.new('Camera',bpy.data.cameras.new('Camera'))
scene.collection.objects.link(camera)
camera.location=center+Vector((0,-height*2.4,height*.03))
camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=height*1.15
scene.camera=camera
for name,offset,power in [('Key',(-.7,-1,.7),40),('Fill',(.8,-.6,.2),12.5)]:
    light=bpy.data.lights.new(name,'AREA')
    light.energy=power*height*height
    light.size=.7*height
    obj=bpy.data.objects.new(name,light)
    scene.collection.objects.link(obj)
    obj.location=center+Vector(offset)*height
    obj.rotation_euler=(center-obj.location).to_track_quat('-Z','Y').to_euler()
scene.world.color=(.05,.05,.05)
scene.render.engine='CYCLES'
scene.cycles.preview_samples=64
scene.cycles.use_preview_denoising=True
prefs=bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type='OPTIX'
prefs.get_devices()
for device in prefs.devices:
    device.use=device.type=='OPTIX'
scene.cycles.device='GPU'
scene.render.resolution_x=scene.render.resolution_y=768
area=next(a for a in bpy.context.screen.areas if a.type=='VIEW_3D')
area.spaces.active.region_3d.view_perspective='CAMERA'
area.spaces.active.overlay.show_overlays=False
area.spaces.active.shading.type='RENDERED'
bpy.context.preferences.view.show_splash=False
cfg=Path(bpy.app.binary_path).parent/'dlss5-feed.cfg'
user32=ctypes.WinDLL('user32',use_last_error=True)
user32.GetForegroundWindow.restype=ctypes.c_void_p
user32.GetWindowThreadProcessId.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)]
started=time.monotonic()
events=[]
done=set()

def enabled(value):
    text=cfg.read_text()
    cfg.write_text('\n'.join('enabled='+str(value) if line.startswith('enabled=') else line for line in text.splitlines())+'\n')

def shot(label):
    pid=ctypes.c_ulong()
    user32.GetWindowThreadProcessId(user32.GetForegroundWindow(),ctypes.byref(pid))
    if pid.value!=os.getpid():
        events.append({'shot':label,'error':'Blender is not foreground; no key sent'})
        return
    user32.keybd_event(0x75,0,0,0)
    def release():
        user32.keybd_event(0x75,0,2,0)
    bpy.app.timers.register(release,first_interval=.2)
    events.append({'shot':label,'seconds':time.monotonic()-started})

def tick():
    elapsed=time.monotonic()-started
    area.tag_redraw()
    for moment,action in [(30,lambda:shot('ON')), (35,lambda:enabled(0)),
                          (43,lambda:shot('OFF')), (48,lambda:enabled(1)),
                          (65,lambda:shot('ON_AGAIN'))]:
        if elapsed>=moment and moment not in done:
            action()
            done.add(moment)
    if elapsed>70:
        (out/'ab.json').write_text(json.dumps({'events':events,'blender':bpy.app.version_string},indent=2))
        bpy.ops.wm.quit_blender()
        return None
    return .05

bpy.app.timers.register(tick,first_interval=1)

