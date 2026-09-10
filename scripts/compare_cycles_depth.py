"""Controlled depth ablation using identical color, settings and fresh NR sessions."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import struct
import sys
import time
import types


def difference(a, b):
    if len(a) != len(b) or len(a) % 4:
        raise ValueError('Mismatched RGBA buffers')
    deltas = [abs(x-y) for i, (x, y) in enumerate(zip(a, b)) if i % 4 != 3]
    return dict(mean_rgb_difference=sum(deltas)/len(deltas),
                max_rgb_difference=max(deltas), changed_channels=sum(d != 0 for d in deltas),
                identical_bytes=a == b)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package = types.ModuleType('_depth_ablation')
    package.__path__ = [str(Path(__file__).resolve().parents[1] / 'addon/cycles_dlss5')]
    sys.modules[package.__name__] = package
    runtime = importlib.import_module(package.__name__ + '.runtime_setup')
    FrameJob = importlib.import_module(package.__name__ + '.frame_job').FrameJob
    validate = importlib.import_module(package.__name__ + '.frame_result').validate_payload
    host, directory = runtime.resolve()
    runtime.verify_files(host, directory)
    original = validate(args.payload)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'cases': {}, 'comparisons': {}, 'quality_improvement_confirmed': False,
              'contract': 'RGBA8; zero motion; reset=1; identical default NR settings',
              'host_sha256': hashlib.sha256(host.read_bytes()).hexdigest(),
              'runtime_files': {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                for name in importlib.import_module(package.__name__ + '.frame_job').RUNTIMES}}
    outputs = {}
    try:
        for case in ('actual', 'actual_repeat', 'far', 'near'):
            folder = args.output / case
            shutil.copytree(args.payload, folder)
            meta = json.loads((folder / 'payload.json').read_text())
            if case in ('far', 'near'):
                depth = struct.pack('<f', 1. if case == 'far' else 0.) * (
                    original['size'][0] * original['size'][1])
                (folder / 'depth.f32').write_bytes(depth)
                meta['files']['depth.f32']['sha256'] = hashlib.sha256(depth).hexdigest()
                meta['guides'] = 'depth ablation: constant ' + case
                meta.pop('valid_depth_pixels', None)
                (folder / 'payload.json').write_text(json.dumps(meta, indent=2))
            for name in ('color.rgba8', 'motion.f16'):
                assert (folder / name).read_bytes() == (args.payload / name).read_bytes()
            job = FrameJob(folder, host, directory)
            try:
                started = time.monotonic()
                job.start()
                while (code := job.poll()) is None:
                    time.sleep(.1)
                result = job.finish(code)
                result['elapsed_seconds'] = time.monotonic() - started
                result['depth_sha256'] = meta['files']['depth.f32']['sha256']
                report['cases'][case] = result
                outputs[case] = (job.work / 'ngx_output.rgba8').read_bytes()
                shutil.copyfile(job.work / 'after.png', folder / 'after.png')
                (folder / 'ngx_output.rgba8').write_bytes(outputs[case])
                print(case, result['confirmation'], flush=True)
            finally:
                if job.process is not None and job.process.poll() is None:
                    job.process.kill()
                    job.process.wait(timeout=5)
                if job.log:
                    job.log.flush()
                for log in job.root.glob('*.log'):
                    shutil.copyfile(log, folder / log.name)
                job.close()
        for case in ('actual_repeat', 'far', 'near'):
            report['comparisons']['actual_vs_' + case] = difference(outputs['actual'], outputs[case])
    finally:
        (args.output / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report['comparisons'], indent=2))


if __name__ == '__main__':
    main()
