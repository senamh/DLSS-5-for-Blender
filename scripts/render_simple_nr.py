"""Two reproducible synthetic Cycles fixtures, no user scene edits."""
import json
from pathlib import Path
import sys
import bpy
from mathutils import Vector

root = Path(sys.argv[sys.argv.index('--')+1])
root.mkdir(parents=True, exist_ok=False)

def material(name, color, metal=0, rough=.4, transmission=0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    node = m.node_tree.nodes.get('Principled BSDF')
    for key, value in {'Base Color': (*color,1), 'Metallic': metal,
                       'Roughness': rough, 'Transmission Weight': transmission}.items():
        node.inputs[key].default_value = value
    return m

def aim(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()

for kind in ('01-matte-forms', '02-metal-glass'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'
    prefs.get_devices()
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    scene.cycles.device = 'GPU' if any(d.use for d in prefs.devices) else 'CPU'
    scene.render.resolution_x, scene.render.resolution_y = 1280, 960
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'AgX'
    world = bpy.data.worlds.new('Neutral environment')
    world.use_nodes = True
    world.node_tree.nodes['Background'].inputs['Color'].default_value = (.3,.35,.45,1)
    world.node_tree.nodes['Background'].inputs['Strength'].default_value = .25
    scene.world = world
    floor = material('Matte floor', (.35,.30,.23), rough=.65)
    bpy.ops.mesh.primitive_plane_add(size=200)
    bpy.context.object.data.materials.append(floor)
    matte = kind == '01-matte-forms'
    mats = ([material('Terracotta', (.5,.12,.055), rough=.75),
             material('Blue clay', (.08,.22,.42), rough=.6),
             material('Ivory clay', (.65,.58,.43), rough=.55)] if matte else
            [material('Copper', (.7,.3,.13), metal=1, rough=.2),
             material('Glass', (.95,.98,1), rough=.06, transmission=1),
             material('Brushed silver', (.65,.7,.75), metal=1, rough=.3)])
    for i, x in enumerate((-2.1,0,2.1)):
        if i == 2:
            bpy.ops.mesh.primitive_monkey_add(location=(x,0,1.05))
            mod = bpy.context.object.modifiers.new('Smooth surface','SUBSURF')
            mod.levels = 2
        else:
            bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32, location=(x,0,1))
        obj = bpy.context.object
        obj.data.materials.append(mats[i])
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
    bpy.ops.object.light_add(type='AREA', location=(-3,-4,6))
    bpy.context.object.data.energy = 1200
    bpy.context.object.data.shape = 'DISK'
    bpy.context.object.data.size = 4
    aim(bpy.context.object,(0,0,1))
    bpy.ops.object.camera_add(location=(6,-11,5.5))
    scene.camera = bpy.context.object
    scene.camera.data.lens = 48
    aim(scene.camera,(0,0,.9))
    folder = root/kind
    folder.mkdir()
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.filepath = str(folder/'01-original.png')
    bpy.ops.wm.save_as_mainfile(filepath=str(folder/'scene.blend'))
    bpy.ops.render.render(write_still=True)
    (folder/'render-settings.json').write_text(json.dumps(dict(scene=kind, samples=64,
        size=[1280,960], view='AgX', denoising=True, device=scene.cycles.device,
        note='Synthetic primitive fixture, not an official Blender demo'), indent=2))
    print('SIMPLE_RENDER_OK', kind, flush=True)
