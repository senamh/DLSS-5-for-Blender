"""Analytical plane fixture; export true engine passes with source-state checks."""
import bpy, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from export_cycles_guides import export_guides
out=Path(sys.argv[sys.argv.index('--')+1]).resolve();out.mkdir(exist_ok=True)
scene=bpy.context.scene
for ob in list(scene.objects):bpy.data.objects.remove(ob,do_unlink=True)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-5))
camera_data=bpy.data.cameras.new('Guide camera');camera=bpy.data.objects.new('Guide camera',camera_data)
scene.collection.objects.link(camera);scene.camera=camera
camera_data.lens=35;camera_data.sensor_width=36;camera_data.sensor_fit='HORIZONTAL'
scene.render.engine='CYCLES';scene.cycles.device='CPU';scene.cycles.use_denoising=False
scene.render.resolution_x=128;scene.render.resolution_y=96;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.filepath='do-not-change'
scene.view_layers[0].use_pass_z=False;scene.view_layers[0].use_pass_vector=False

def state():return {'scenes':len(bpy.data.scenes),'format':scene.render.image_settings.file_format,
    'filepath':scene.render.filepath,'z':scene.view_layers[0].use_pass_z,
    'vector':scene.view_layers[0].use_pass_vector,'frame':scene.frame_current}
reports=[]
for name,kind,samples in [('perspective_1','PERSP',1),('perspective_8','PERSP',8),('orthographic_1','ORTHO',1)]:
    camera_data.type=kind;scene.cycles.samples=samples
    before=state();export_guides(scene,out/name);after=state()
    assert before==after,(before,after)
    reports.append({'case':name,'source_unchanged':True})
(out/'source-state.json').write_text(json.dumps(reports,indent=2))

