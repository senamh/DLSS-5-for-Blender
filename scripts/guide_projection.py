"""Projection conversion only; no image filter or inferred geometry."""
import numpy as np


def camera_z_to_device_depth(depth, projection, reversed_z=False):
    """Positive axial Cycles Z -> OpenGL [0,1] depth; out-of-frustum -> far.

    Restricted to Blender PERSP/ORTHO calc_matrix_camera matrices. The caller
    must bind this convention explicitly in the runtime; auto-detection is unsafe.
    """
    z=np.asarray(depth,dtype=np.float64)
    p=np.asarray(projection,dtype=np.float64)
    if p.shape!=(4,4) or not np.isfinite(p).all():raise ValueError('Invalid projection matrix')
    if np.any(np.abs(p[2:4,0:2])>1e-8):raise ValueError('Oblique depth projection is unsupported')
    with np.errstate(divide='ignore',invalid='ignore'):
        value=.5*((-p[2,2]*z+p[2,3])/(-p[3,2]*z+p[3,3]))+.5
    valid=np.isfinite(z)&(z>0)&np.isfinite(value)&(value>=0)&(value<=1)
    value=np.where(valid,value,1.0)
    if reversed_z:value=1.0-value
    return value.astype(np.float32),valid

