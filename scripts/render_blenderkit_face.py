"""Render the attributed BlenderKit sculpt with original materials, no embedded scripts."""
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

root = Path(sys.argv[sys.argv.index('--')+1])
with bpy.data.libraries.load(str(root/'source.blend'), link=False) as (source, target):
    target.objects = source.objects
for obj in list(bpy.context.scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
for obj in target.objects:
    if obj is not None:
        bpy.context.scene.collection.objects.link(obj)
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert meshes
bpy.context.view_layer.update()
points = [o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
low = Vector([min(p[i] for p in points) for i in range(3)])
high = Vector([max(p[i] for p in points) for i in range(3)])
center = (low+high)/2
height = high.z-low.z
assert height > 0
scene = bpy.context.scene
def aim(obj):
    obj.rotation_euler = (center-obj.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=center+Vector((0,-height*2.5,height*.02)))
scene.camera = bpy.context.object
aim(scene.camera)
scene.camera.data.type = 'ORTHO'
scene.camera.data.ortho_scale = max(height,high.x-low.x)*1.2
for offset, power in [((-.7,-1,.7),40), ((.8,-.6,.2),12.5)]:
    bpy.ops.object.light_add(type='AREA', location=center+Vector(offset)*height)
    lamp = bpy.context.object
    lamp.data.energy = power*height*height
    lamp.data.size = height*.7
    aim(lamp)
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .2
scene.render.engine = 'CYCLES'
scene.cycles.samples = 64
scene.cycles.use_denoising = True
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
for d in prefs.devices:
    d.use = d.type == 'OPTIX'
scene.cycles.device = 'GPU' if any(d.use for d in prefs.devices) else 'CPU'
scene.render.resolution_x = scene.render.resolution_y = 1280
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'AgX'
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.color_depth = '8'
scene.render.filepath = str(root/'01-original.png')
bpy.ops.render.render(write_still=True)
(root/'render-settings.json').write_text(json.dumps(dict(author='diaverx miky',
    asset='Male Head 3D Sculpt', asset_id='a7a5b28c-e1dc-4262-9768-7831a0d5bf21',
    url='https://www.blendkit.com/asset-gallery-detail/a7a5b28c-e1dc-4262-9768-7831a0d5bf21/',
    license='royalty_free', size=[1280,1280], samples=64, view='AgX',
    materials='original asset materials', bounds=[list(low),list(high)]), indent=2))
print('BLENDERKIT_FACE_RENDER_OK')
