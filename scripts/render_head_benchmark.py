"""Create a disposable Cycles portrait from the attributed Lee Perry-Smith scan."""
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector
import numpy as np

root = Path(sys.argv[sys.argv.index('--')+1])
size = int(sys.argv[sys.argv.index('--')+2]) if len(sys.argv) > sys.argv.index('--')+2 else 768
assert 96 <= size <= 4096
assets = root/'assets'
for obj in list(bpy.data.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(assets/'LeePerrySmith.glb'))
meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
assert meshes, 'No head mesh imported'
mat = bpy.data.materials.new('Lee Perry-Smith scan skin')
mat.use_nodes = True
nodes = mat.node_tree.nodes
shader = nodes.get('Principled BSDF')
shader.inputs['Roughness'].default_value = .5
shader.inputs['Subsurface Weight'].default_value = .07
diffuse = nodes.new('ShaderNodeTexImage')
diffuse.image = bpy.data.images.load(str(assets/'Map-COL.jpg'))
mat.node_tree.links.new(diffuse.outputs['Color'], shader.inputs['Base Color'])
tex = nodes.new('ShaderNodeTexImage')
tex.image = bpy.data.images.load(str(assets/'Infinite-Level_02_Tangent_SmoothUV.jpg'))
tex.image.colorspace_settings.name = 'Non-Color'
# glTF import flips UV V; these separately loaded maps use the glTF convention.
uv = nodes.new('ShaderNodeTexCoord')
flip = nodes.new('ShaderNodeVectorMath')
flip.operation = 'MULTIPLY_ADD'
flip.inputs[1].default_value = (1,-1,1)
flip.inputs[2].default_value = (0,1,0)
mat.node_tree.links.new(uv.outputs['UV'], flip.inputs[0])
mat.node_tree.links.new(flip.outputs['Vector'], diffuse.inputs['Vector'])
mat.node_tree.links.new(flip.outputs['Vector'], tex.inputs['Vector'])
normal = nodes.new('ShaderNodeNormalMap')
mat.node_tree.links.new(tex.outputs['Color'], normal.inputs['Color'])
mat.node_tree.links.new(normal.outputs['Normal'], shader.inputs['Normal'])
for obj in meshes:
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
bpy.context.view_layer.update()
points = [o.matrix_world@Vector(c) for o in meshes for c in o.bound_box]
low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
center = (low+high)/2
height = high.z-low.z
scene = bpy.context.scene
camera = bpy.data.objects.new('Portrait camera', bpy.data.cameras.new('Portrait camera'))
scene.collection.objects.link(camera)
camera.location = center+Vector((0, -height*2.4, height*.03))
camera.rotation_euler = (center-camera.location).to_track_quat('-Z', 'Y').to_euler()
camera.data.type = 'ORTHO'
camera.data.ortho_scale = height*1.12
scene.camera = camera
for name, offset, power, light_size in [('Key', (-.7,-1, .7), 40, .7), ('Fill', (.8,-.6,.2), 12.5, .9)]:
    light = bpy.data.lights.new(name, 'AREA')
    light.energy = power*height*height
    light.size = light_size*height
    obj = bpy.data.objects.new(name, light)
    scene.collection.objects.link(obj)
    obj.location = center+Vector(offset)*height
    obj.rotation_euler = (center-obj.location).to_track_quat('-Z','Y').to_euler()
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.15,.15,.15,1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .3
scene.render.engine = 'CYCLES'
scene.cycles.samples = 64
scene.cycles.use_denoising = True
scene.cycles.device = 'CPU'
prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    if any(d.use for d in prefs.devices):
        scene.cycles.device = 'GPU'
except Exception:
    pass
scene.render.resolution_x = scene.render.resolution_y = size
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = 'AgX'
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.color_depth = '16'
scene.render.filepath = str(root/'original.png')
bpy.ops.render.render(write_still=True)
# Feed the model the same display-referred portrait the viewer sees.
image = bpy.data.images.load(str(root/'original.png'), check_existing=False)
image.colorspace_settings.name = 'Non-Color'
frame = np.empty(size*size*4, dtype=np.float32)
image.pixels.foreach_get(frame)
frame = frame.reshape(size,size,4)
rgb = np.maximum(frame[:,:,:3],0)
frame[:,:,:3] = np.where(rgb<=.04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
np.save(root/'input.npy',frame,allow_pickle=False)
(root/'render.json').write_text(json.dumps(dict(blender=bpy.app.version_string,
    device=scene.cycles.device, bounds=[list(low),list(high)], samples=64, size=[size,size],
    view_transform='AgX', source='Lee Perry-Smith / Infinite, CC BY 3.0; three.js examples'),indent=2))
