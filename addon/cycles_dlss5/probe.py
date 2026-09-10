"""Isolated native execution probe; also runnable with ordinary Windows Python.

No DLL is loaded on import. This is execution evidence, not a security attestation.
"""
import argparse
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

SCHEMA = 1
CONTRACT = 'independent-reinhard-v1'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def identity(runtime, bridge, order):
    if order not in ('RGB', 'BGR'):
        raise ValueError('Choose RGB or BGR output order')
    result = subprocess.run(
        ['nvidia-smi', '--query-gpu=name,uuid,driver_version', '--format=csv,noheader'],
        capture_output=True, text=True, check=True, timeout=10,
    )
    devices = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    # The current Cycles ABI selects NVIDIA adapter 0; multiple adapters need
    # explicit UUID/LUID routing before a receipt can safely cover that path.
    if len(devices) != 1:
        raise ValueError('Execution validation currently requires one NVIDIA GPU')
    runtime = Path(runtime).resolve(strict=True)
    bridge = Path(bridge).resolve(strict=True)
    files = {
        'runtime': runtime / 'nvngx_dlssnr.dll',
        'shim': runtime / 'caller' / 'nvngx.dll_blender.dll',
        'bridge': bridge,
    }
    core = runtime / '_nvngx.dll'
    if core.is_file():
        files['core_override'] = core
    return {
        'contract': CONTRACT, 'order': order, 'devices': devices,
        'runtime_path': str(runtime), 'bridge_path': str(bridge),
        'hashes': {key: digest(path) for key, path in files.items()},
        'probe_sha256': digest(__file__),
    }


def require_receipt(path, expected):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError('Run the isolated runtime test first')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError('Runtime test report cannot be read; run it again') from error
    if (not isinstance(data, dict) or data.get('schema') != SCHEMA or
            data.get('passed') is not True or data.get('identity') != expected):
        raise ValueError('Runtime test is missing, failed or stale; run it again')
    return data


def chart(width=128, height=128):
    values = []
    for y in range(height):
        for x in range(width):
            channel = min(2, x * 3 // width)
            level = 0.25 + 0.5 * y / (height - 1)
            values.extend(level if c == channel else 0.025 for c in range(3))
    return values


def stats(source, result, width=128, height=128):
    if len(result) != len(source) or not all(math.isfinite(x) and x >= 0 for x in result):
        raise ValueError('Runtime returned invalid pixels')
    delta = sum(abs(a - b) for a, b in zip(source, result)) / len(source)
    if delta < 1e-5:
        raise ValueError('No measurable image change; neural processing is unconfirmed')
    # Coarse channel sanity check, not colorimetric/HDR certification.
    for band in range(3):
        sums = [0.0, 0.0, 0.0]
        for y in range(height // 4, height * 3 // 4):
            for x in range(band * width // 3 + 8, (band + 1) * width // 3 - 8):
                i = (y * width + x) * 3
                for c in range(3):
                    sums[c] += result[i + c]
        if sums[band] <= max(sums[c] for c in range(3) if c != band):
            raise ValueError('Color chart failed: check RGB/BGR order and runtime')
    return {'mean_absolute_change': delta, 'maximum': max(result)}


def save_preview(path, values):
    # Display preview only; the native float output remains in output.f32.
    pixels = bytes(round(min(1.0, max(0.0, x)) ** (1 / 2.2) * 255) for x in values)
    Path(path).write_bytes(b'P6\n128 128\n255\n' + pixels)


def worker(runtime, bridge, order, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    report = {'schema': SCHEMA, 'passed': False, 'scope': '128x128 synthetic independent frames'}
    try:
        if sys.platform != 'win32':
            raise ValueError('Native execution requires Windows x64')
        report['identity'] = identity(runtime, bridge, order)
        os.environ['CYCLES_DLSS5NR_OUTPUT_ORDER'] = order
        dll = ctypes.CDLL(str(Path(bridge).resolve(strict=True)))
        dll.dlss5nr_version.restype = ctypes.c_char_p
        if dll.dlss5nr_version() != b'0.5.0-independent-frames':
            raise ValueError('Rebuild the bridge: this probe requires version 0.5.0')
        dll.dlss5nr_init.argtypes = [ctypes.c_int, ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_int]
        dll.dlss5nr_init.restype = ctypes.c_int
        dll.dlss5nr_process.argtypes = [ctypes.POINTER(ctypes.c_float)] * 2 + [ctypes.c_int] * 4 + [ctypes.c_float] * 4 + [ctypes.c_int] * 2 + [ctypes.c_void_p, ctypes.c_int]
        dll.dlss5nr_process.restype = ctypes.c_int
        dll.dlss5nr_shutdown.argtypes = []
        dll.dlss5nr_shutdown.restype = None
        dll.dlss5nr_gpu_name.restype = ctypes.c_char_p
        error = ctypes.create_string_buffer(4096)
        if not dll.dlss5nr_init(0, str(Path(runtime).resolve()), error, len(error)):
            raise ValueError(error.value.decode('utf-8', 'replace'))
        report['native_gpu'] = dll.dlss5nr_gpu_name().decode('utf-8', 'replace')
        source = chart()
        timings = []
        def evaluate(values):
            incoming = (ctypes.c_float * len(values))(*values)
            outgoing = (ctypes.c_float * len(values))(*([float('nan')] * len(values)))
            start = time.perf_counter()
            ok = dll.dlss5nr_process(incoming, outgoing, 128, 128, 1, 0, 1., 1., 1., -1., 0, 1, error, len(error))
            timings.append((time.perf_counter() - start) * 1000)
            if not ok:
                raise ValueError(error.value.decode('utf-8', 'replace'))
            return list(outgoing)
        first = evaluate(source)
        report['pixels'] = stats(source, first)
        evaluate(list(reversed(source)))
        repeated = evaluate(source)
        difference = max(abs(a - b) for a, b in zip(first, repeated))
        if not all(math.isfinite(x) for x in repeated) or difference > 1e-4:
            raise ValueError('Independent A/B/A frame test failed')
        report['repeat_max_difference'] = difference
        report['evaluation_ms'] = timings
        save_preview(output / 'input.ppm', source)
        save_preview(output / 'output.ppm', first)
        (output / 'output.f32').write_bytes(bytes((ctypes.c_float * len(first))(*first)))
        dll.dlss5nr_shutdown()
        if report['identity'] != identity(runtime, bridge, order):
            raise ValueError('Files or GPU configuration changed during the test')
        report['passed'] = True
        report['limitations'] = 'Not proof of HDR fidelity, Blender integration, temporal stability or realtime FPS'
    except Exception as error:
        report['error'] = str(error)
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if report['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--bridge', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--order', choices=['RGB', 'BGR'], default='RGB')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--trust-runtime', action='store_true')
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    if not args.trust_runtime:
        parser.error('Explicit --trust-runtime is required before loading native files')
    if args.worker:
        return worker(args.runtime, args.bridge, args.order, args.output)
    # Parent never loads the library. A native crash or timeout cannot yield success.
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=False)
    command = [sys.executable, str(Path(__file__).resolve()), *argv, '--worker']
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=120)
        (destination / 'worker.log').write_text(result.stdout + result.stderr, encoding='utf-8')
        if result.returncode:
            raise ValueError(f'Native worker failed: exit {result.returncode}')
        require_receipt(destination / 'report.json', identity(args.runtime, args.bridge, args.order))
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        # Keep the native failure detail before writing the parent verdict.
        child_report = destination / 'report.json'
        if child_report.is_file():
            child_report.replace(destination / 'worker-report.json')
        (destination / 'report.json').write_text(json.dumps({'schema': SCHEMA, 'passed': False, 'error': str(error)}), encoding='utf-8')
        print(error, file=sys.stderr)
        return 1
    print(destination / 'report.json')
    return 0


if __name__ == '__main__':
    exit_code = main()
    if exit_code:
        raise SystemExit(exit_code)

