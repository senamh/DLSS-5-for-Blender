"""Process one linear RGBA frame in a disposable stock Blender process."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
import time

import numpy as np

if __package__:
    from .style_config import native_values, PRESETS, FIELDS
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from style_config import native_values, PRESETS, FIELDS

_dll = None
_configuration = None


def process(job_path):
    global _dll, _configuration
    job = json.loads(Path(job_path).read_text(encoding='utf-8'))
    settings = native_values(job.get('settings', dict(zip(FIELDS, PRESETS['BALANCED']))))
    os.environ['CYCLES_DLSS5NR_OUTPUT_ORDER'] = job['order']
    color_mode = job.get('color_mode', 'HDR_TRANSFER')
    if color_mode not in {'DISPLAY_LINEAR', 'HDR_TRANSFER'}:
        raise ValueError('Unknown stock color mode')
    os.environ['CYCLES_DLSS5NR_COLOR_MODE'] = color_mode
    frame = np.load(job['input'], allow_pickle=False)
    if frame.ndim != 3 or frame.shape[2] != 4 or not np.isfinite(frame).all():
        raise ValueError('Expected finite linear RGBA input')
    height, width, _ = frame.shape
    if not (96 <= width <= 4096 and 96 <= height <= 4096):
        raise ValueError('Supported dimensions: 96..4096 on each side')
    incoming = np.ascontiguousarray(frame[:, :, :3], dtype=np.float32)
    outgoing = np.full_like(incoming, np.nan)
    configuration = (job['bridge'], job['runtime'], job['order'], color_mode)
    if _configuration is not None and configuration != _configuration:
        raise ValueError('Restart worker after changing runtime configuration')
    dll = _dll or ctypes.CDLL(job['bridge'])
    dll.dlss5nr_version.restype = ctypes.c_char_p
    if dll.dlss5nr_version() != b'0.5.0-independent-frames':
        raise ValueError('Bridge version does not match this addon')
    if not hasattr(dll, 'dlss5nr_color_codec_version') or dll.dlss5nr_color_codec_version() != 1:
        raise ValueError('Update the native bridge: stock color codec is missing')
    dll.dlss5nr_init.argtypes = [ctypes.c_int, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_int]
    dll.dlss5nr_init.restype = ctypes.c_int
    ptr = ctypes.POINTER(ctypes.c_float)
    dll.dlss5nr_process.argtypes = [ptr, ptr] + [ctypes.c_int]*4 + [ctypes.c_float]*4 + [ctypes.c_int]*2 + [ctypes.c_void_p, ctypes.c_int]
    dll.dlss5nr_process.restype = ctypes.c_int
    dll.dlss5nr_shutdown.argtypes = []
    dll.dlss5nr_gpu_name.restype = ctypes.c_char_p
    error = ctypes.create_string_buffer(4096)
    if _dll is None and not dll.dlss5nr_init(0, job['runtime'], error, len(error)):
        raise RuntimeError(error.value.decode('utf-8', 'replace'))
    _dll, _configuration = dll, configuration
    try:
        if not dll.dlss5nr_process(incoming.ctypes.data_as(ptr), outgoing.ctypes.data_as(ptr),
                                 width, height, int(settings['NRStyle']), 0,
                                 float(settings['NRIntensity']), float(settings['NRLocalTone']),
                                 float(settings['NRLocalStructure']), float(settings['NRSkinStructure']),
                                 int(settings['NRAutoMask']), 1, error, len(error)):
            raise RuntimeError(error.value.decode('utf-8', 'replace'))
        if not np.isfinite(outgoing).all():
            raise ValueError('Runtime returned nonfinite pixels')
        result = np.array(frame, dtype=np.float32, copy=True)
        result[:, :, :3] = outgoing
        output_path = Path(job['output'])
        temporary = output_path.with_suffix('.tmp')
        with temporary.open('wb') as stream:
            np.save(stream, result, allow_pickle=False)
        temporary.replace(output_path)
        return {'native_settings': settings, 'pid': os.getpid(),
                'bridge_version': dll.dlss5nr_version().decode(),
                'gpu': dll.dlss5nr_gpu_name().decode(), 'reset': True,
                'input_sha256': hashlib.sha256(frame.tobytes()).hexdigest(),
                'output_sha256': hashlib.sha256(result.tobytes()).hexdigest(),
                'temporal_accumulation': False}
    finally:
        pass  # The worker owns the initialized runtime for its entire lifetime.


def serve(job_path):
    root = Path(job_path).parent
    previous = 0
    while not (root/'stop').exists():
        request = root/f'request-{previous+1}.json'
        if not request.exists():
            time.sleep(.01)
            continue
        try:
            sequence = json.loads(request.read_text(encoding='utf-8'))['sequence']
        except PermissionError:
            # A transient Windows file-sharing lock is not a runtime failure.
            time.sleep(.01)
            continue
        if type(sequence) is not int or sequence != previous + 1:
            raise ValueError('Unexpected request sequence')
        started = time.monotonic()
        report = process(job_path) or {}
        temporary = root/'done.tmp'
        temporary.write_text(json.dumps({**report, 'sequence': sequence,
            'seconds': time.monotonic()-started}), encoding='utf-8')
        temporary.replace(root/f'done-{sequence}.json')
        previous = sequence


if __name__ == '__main__':
    try:
        job_path = sys.argv[sys.argv.index('--') + 1]
        if '--serve' in sys.argv:
            serve(job_path)
        else:
            process(job_path)
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
    finally:
        if _dll is not None:
            _dll.dlss5nr_shutdown()
