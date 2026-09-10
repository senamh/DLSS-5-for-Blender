"""Disposable material scene; never called by the artist launcher."""
import bpy

def setup():
    cube = bpy.data.objects.get('Cube')
    if cube:
        cube.scale = (0.6, 0.6, 0.6)
    for x, metal in [(-1.5, 0.0), (1.5, 1.0)]:
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, location=(x, 0, 0))
        obj = bpy.context.object
        for polygon in obj.data.polygons:
            polygon.use_smooth = True
        mat = bpy.data.materials.new('Textured metal' if metal else 'Textured warm surface')
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        bsdf = nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (0.45, 0.18, 0.08, 1)
        bsdf.inputs['Metallic'].default_value = metal
        bsdf.inputs['Roughness'].default_value = 0.25
        noise = nodes.new('ShaderNodeTexNoise')
        noise.inputs['Scale'].default_value = 80
        bump = nodes.new('ShaderNodeBump')
        bump.inputs['Strength'].default_value = 0.3
        bump.inputs['Distance'].default_value = 0.025
        mat.node_tree.links.new(noise.outputs['Fac'], bump.inputs['Height'])
        mat.node_tree.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
        obj.data.materials.append(mat)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -1.05))
    lamp = bpy.data.lights.new('Softbox', 'AREA')
    lamp.energy = 1200
    lamp.shape = 'DISK'
    lamp.size = 4
    obj = bpy.data.objects.new('Softbox', lamp)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = (0, 0, 5)

