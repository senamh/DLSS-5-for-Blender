"""Package Blender display color + true Cycles depth for upstream host's still mode."""
import hashlib,json,sys
from pathlib import Path
import numpy as np
import OpenEXR
from PIL import Image
from guide_projection import camera_z_to_device_depth


def prepare(source,destination,layer,*,independent_frame=False):
    source=Path(source);destination=Path(destination)
    meta=json.loads((source/'metadata.json').read_text())
    if meta.get('schema')!=1 or meta.get('camera_type') not in {'PERSP','ORTHO'}:
        raise ValueError('Unsupported render guide metadata')
    w,h=meta['size']
    if not (96<=w<=4096 and 96<=h<=4096):raise ValueError('Still host dimensions must be 96..4096')
    exr=OpenEXR.File(str(source/'passes.exr'),separate_channels=True)
    channels={}
    for part in exr.parts:
        for name,channel in part.channels.items():
            if name in channels:raise ValueError('Ambiguous EXR channel: '+name)
            channels[name]=channel.pixels
    def get(pass_name,suffix):
        name=f'{layer}.{pass_name}.{suffix}'
        if name not in channels:raise ValueError('Missing actual Cycles pass: '+name)
        a=np.asarray(channels[name],np.float32)
        if a.shape!=(h,w):raise ValueError('Pass dimensions disagree with metadata')
        return a
    z=get('Depth','Z')
    motion=np.stack([get('Vector',c) for c in 'XYZW'],axis=-1)
    if not np.isfinite(motion).all():
        raise ValueError('Cycles Vector pass contains nonfinite values')
    has_motion = bool(np.any(motion!=0))
    if has_motion and not independent_frame:
        raise ValueError('Animated input needs temporal motion conversion; still mode refuses it')
    if meta.get('display_color',{}).get('display')!='sRGB':
        raise ValueError('SDR host currently requires Blender sRGB display output')
    color=np.asarray(Image.open(source/'display.png').convert('RGBA'),np.uint8)
    if color.shape!=(h,w,4):raise ValueError('Display image dimensions disagree with guides')
    if np.any(color[:,:,3]!=255):raise ValueError('Transparent output needs explicit compositing/alpha handling')
    if len([n for n in channels if '.Combined.R' in n])!=1:
        raise ValueError('Display color with multiple view layers needs explicit layer selection')
    depth,valid=camera_z_to_device_depth(z,meta['projection'])
    if not valid.any():raise ValueError('No valid geometry depth: refusing an empty guide')
    destination.mkdir(parents=True,exist_ok=False)
    arrays={'color.rgba8':color,'depth.f32':depth.astype('<f4'),
            'motion.f16':np.zeros((h,w,2),dtype='<f2')}
    files={}
    for name,array in arrays.items():
        data=np.ascontiguousarray(array).tobytes();(destination/name).write_bytes(data)
        files[name]={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
    payload={'schema':1,'size':[w,h],'layer':layer,'origin':'top-left',
        'color':'Blender display sRGB RGBA8; no additional tone mapping',
        'depth':'normal device depth [0,1] R32F; far=1',
        'motion':('RG16F zero; independent frame, source vectors not consumed'
                  if independent_frame else 'RG16F zero, validated static source'),
        'source_has_motion':has_motion,'reset':True,
        'guides':'actual Cycles device depth; no temporal accumulation',
        'valid_depth_pixels':int(valid.sum()),'files':files,'dlss_applied':False}
    (destination/'payload.json').write_text(json.dumps(payload,indent=2))
    return payload

if __name__=='__main__':
    print(json.dumps(prepare(sys.argv[1],sys.argv[2],sys.argv[3]),indent=2))
