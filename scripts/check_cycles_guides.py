"""Inspect standard OpenEXR engine output; reject missing/nonfinite depth."""
import json,sys
from pathlib import Path
import OpenEXR
import numpy as np
from guide_projection import camera_z_to_device_depth
root=Path(sys.argv[1]);report=[]
for folder in sorted(p for p in root.iterdir() if p.is_dir()):
    meta=json.loads((folder/'metadata.json').read_text())
    exr=OpenEXR.File(str(folder/'passes.exr'),separate_channels=True)
    channels={name:channel for part in exr.parts for name,channel in part.channels.items()}
    names=list(channels)
    depth_name=next(n for n in names if '.Depth.' in n)
    vector_names=[n for n in names if '.Vector.' in n]
    assert len(vector_names)==4,names
    w,h=meta['size'];z=np.asarray(channels[depth_name].pixels,dtype=np.float32).reshape(h,w)
    assert np.isfinite(z).all() and (z>0).all()
    # Compare the center and edge against both possible depth conventions.
    rows=z[h//2];camera_z=np.full(w,5.0)
    x=((np.arange(w)+.5)/w*2-1)*18/35
    y=(.5/h)*2*(18/35)*(h/w)
    ray_distance=5*np.sqrt(1+x*x+y*y)
    if meta['camera_type']=='ORTHO':ray_distance=camera_z
    axial_error=float(np.max(np.abs(rows-camera_z)))
    ray_error=float(np.max(np.abs(rows-ray_distance)))
    assert min(axial_error,ray_error)<.06,(folder.name,axial_error,ray_error)
    # Cycles source camera_z_depth confirms axial depth for PERSP and ORTHO.
    assert axial_error<1e-4,(folder.name,axial_error)
    device,valid=camera_z_to_device_depth(z,meta['projection'])
    near,far=meta['clip']
    expected=(5-near)/(far-near) if meta['camera_type']=='ORTHO' else far/(far-near)-(far*near)/((far-near)*5)
    assert valid.all() and float(np.max(np.abs(device-expected)))<1e-5
    reversed_depth,_=camera_z_to_device_depth(z,meta['projection'],True)
    assert float(np.max(np.abs(device+reversed_depth-1)))<1e-6
    np.save(folder/'device_depth.npy',device)
    np.save(folder/'depth.npy',z)
    report.append({'case':folder.name,'depth_min':float(z.min()),'depth_max':float(z.max()),
        'center':float(rows[w//2]),'edge':float(rows[0]),'axial_error':axial_error,
        'ray_distance_error':ray_error,'device_depth':float(device[h//2,w//2]),'vector_channels':vector_names,'dlss_applied':False})
(root/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

