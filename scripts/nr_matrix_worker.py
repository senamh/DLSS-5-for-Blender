"""Isolated diagnostic worker, run by stock Blender for its NumPy dependency."""
import ctypes
import json
import os
from pathlib import Path
import sys
import time

import numpy as np

job = json.loads(Path(sys.argv[sys.argv.index('--')+1]).read_text())
os.environ['CYCLES_DLSS5NR_OUTPUT_ORDER'] = 'RGB'
os.environ['CYCLES_DLSS5NR_COLOR_MODE'] = 'DISPLAY_LINEAR'
frame = np.load(job['input'], allow_pickle=False)
assert frame.ndim == 3 and frame.shape[2] == 4 and np.isfinite(frame).all()
rgb = np.ascontiguousarray(frame[:, :, :3], dtype=np.float32)
out = np.full_like(rgb, np.nan)
ptr = ctypes.POINTER(ctypes.c_float)
dll = ctypes.CDLL(job['bridge'])
dll.dlss5nr_init.argtypes = [ctypes.c_int, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_int]
dll.dlss5nr_process.argtypes = [ptr, ptr] + [ctypes.c_int]*4 + [ctypes.c_float]*4 + [ctypes.c_int]*2 + [ctypes.c_void_p, ctypes.c_int]
dll.dlss5nr_gpu_name.restype = ctypes.c_char_p
error = ctypes.create_string_buffer(4096)
started = time.monotonic()
assert dll.dlss5nr_init(0, job['runtime'], error, len(error)), error.value
try:
    assert dll.dlss5nr_process(rgb.ctypes.data_as(ptr), out.ctypes.data_as(ptr),
        rgb.shape[1], rgb.shape[0], job['style'], 0, job['intensity'], job.get('tone',1.), job.get('structure',1.), job.get('skin',-1.),
        job.get('automask',0), 1, error, len(error)), error.value
    assert np.isfinite(out).all()
    np.save(job['output'], out, allow_pickle=False)
    # Also distinguish actual structural changes from a global brightness gain.
    gain = float(np.sum(rgb.astype(np.float64)*out)/max(1e-12, np.sum(rgb.astype(np.float64)**2)))
    report = dict(gpu=dll.dlss5nr_gpu_name().decode(), seconds=time.monotonic()-started,
        mean_absolute_change=float(np.mean(np.abs(out-rgb))), fitted_gain=gain,
        residual_after_gain=float(np.mean(np.abs(out-gain*rgb))),
        changed_fraction=float(np.mean(np.max(np.abs(out-rgb), axis=2)>.01)))
    Path(job['report']).write_text(json.dumps(report, indent=2))
finally:
    dll.dlss5nr_shutdown()

