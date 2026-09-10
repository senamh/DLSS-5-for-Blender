"""Export actual Cycles passes from an isolated scene copy; no neural processing."""
import json
from pathlib import Path
import bpy


def export_guides(source, destination):
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=False)
    scene=source.copy()
    try:
        if scene.camera is None:raise ValueError('The scene needs a camera')
        if scene.camera.data.type not in {'PERSP','ORTHO'}:
            raise ValueError('Panoramic cameras need a separate guide projection contract')
        scene.render.engine='CYCLES'
        scene.use_nodes=False  # Export engine passes, not user compositor output.
        scene.render.use_compositing=False
        scene.render.use_sequencer=False
        scene.render.use_border=False
        scene.render.use_multiview=False
        scene.render.use_motion_blur=False  # Required for an unblurred Vector pass.
        for layer in scene.view_layers:
            layer.use_pass_z=True
            layer.use_pass_vector=True
        scene.render.image_settings.media_type='MULTI_LAYER_IMAGE'
        scene.render.image_settings.file_format='OPEN_EXR_MULTILAYER'
        scene.render.image_settings.color_depth='32'
        scene.render.image_settings.exr_codec='ZIP'
        scene.render.filepath=str(destination/'passes.exr')
        scene.render.use_file_extension=True
        bpy.ops.render.render(scene=scene.name,write_still=True)
        assert (destination/'passes.exr').is_file(),'Cycles did not write the multilayer EXR'
        # Use Blender's own scene display transform, not a custom tone mapper.
        scene.render.image_settings.media_type='IMAGE'
        scene.render.image_settings.file_format='PNG'
        scene.render.image_settings.color_depth='8'
        scene.render.image_settings.color_mode='RGBA'
        bpy.data.images['Render Result'].save_render(str(destination/'display.png'),scene=scene)
        with bpy.context.temp_override(scene=scene):
            depsgraph=bpy.context.evaluated_depsgraph_get()
            width=max(1,int(scene.render.resolution_x*scene.render.resolution_percentage/100))
            height=max(1,int(scene.render.resolution_y*scene.render.resolution_percentage/100))
            projection=scene.camera.calc_matrix_camera(depsgraph,x=width,y=height,
                scale_x=scene.render.pixel_aspect_x,scale_y=scene.render.pixel_aspect_y)
        metadata={'schema':1,'blender':bpy.app.version_string,'source_scene':source.name,
            'view_layers':[layer.name for layer in scene.view_layers if layer.use],
            'frame':scene.frame_current,'size':[width,height],'camera_type':scene.camera.data.type,
            'clip':[scene.camera.data.clip_start,scene.camera.data.clip_end],
            'camera_world':[list(r) for r in scene.camera.matrix_world],
            'projection':[list(r) for r in projection],
            'color':'scene-linear Combined; no display transform',
            'display_color':{'file':'display.png','display':scene.display_settings.display_device,
                'view':scene.view_settings.view_transform,'look':scene.view_settings.look,
                'exposure':scene.view_settings.exposure,'gamma':scene.view_settings.gamma},
            'depth':'raw Cycles Depth pass; not normalized device depth',
            'motion':'raw Cycles four-component Vector pass; not yet converted to DLSS motion',
            'render_overrides':['compositor off','sequencer off','border off','multiview off','motion blur off'],
            'dlss_applied':False}
        (destination/'metadata.json').write_text(json.dumps(metadata,indent=2))
        return metadata
    finally:
        bpy.data.scenes.remove(scene)
