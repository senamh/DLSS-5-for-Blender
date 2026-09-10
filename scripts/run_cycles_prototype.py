"""Reproducible static Cycles depth -> NR experiment; never installs an addon.

Requires NumPy, Pillow and OpenEXR in this Python interpreter. Blender runs in
a separate factory-startup process with embedded scripts disabled. All evidence
is retained; output must be a new directory. Native output remains SDR until a
different color contract is measured and verified.
"""
import argparse
import importlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import types

from prepare_frame_payload import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender', required=True, type=Path)
    parser.add_argument('--blend', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--long-side', type=int, default=512)
    parser.add_argument('--samples', type=int, default=8)
    parser.add_argument('--layer')
    parser.add_argument('--runtime', default='')
    parser.add_argument('--host', default='')
    args = parser.parse_args()
    if not 128 <= args.long_side <= 4096 or not 1 <= args.samples <= 4096:
        parser.error('Invalid test resolution or samples')
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'nr_confirmed': False, 'quality_improvement_confirmed': False,
              'hdr_verified': False, 'temporal_verified': False}
    job = None
    try:
        root = Path(__file__).resolve().parents[1]
        package = types.ModuleType('_cycles_prototype')
        package.__path__ = [str(root / 'addon/cycles_dlss5')]
        sys.modules[package.__name__] = package
        runtime = importlib.import_module(package.__name__ + '.runtime_setup')
        host, runtime_dir = runtime.resolve(args.runtime, args.host)
        runtime.verify_files(host, runtime_dir)
        config = out / 'render.json'
        config.write_text(json.dumps(dict(export=str(out / 'cycles'),
            samples=args.samples, long_side=args.long_side)), encoding='utf-8')
        command = [str(args.blender), '--background', '--factory-startup', '--disable-autoexec']
        if args.blend:
            command.append(str(args.blend.resolve()))
        command += ['--python-exit-code', '1', '--python',
                    str(root / 'scripts/render_cycles_prototype.py'), '--', str(config)]
        with (out / 'cycles.log').open('w', encoding='utf-8') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
        exported = json.loads((out / 'cycles/metadata.json').read_text())
        layers = exported['view_layers']
        if len(layers) != 1:
            raise ValueError('Prototype requires a single enabled view layer for matched color/depth')
        meta = prepare(out / 'cycles', out / 'payload', args.layer or layers[0],
                       independent_frame=True)
        report['payload'] = meta
        FrameJob = importlib.import_module(package.__name__ + '.frame_job').FrameJob
        job = FrameJob(out / 'payload', host, runtime_dir)
        job.start()
        while (code := job.poll()) is None:
            time.sleep(.1)
        report.update(job.finish(code))
        report['depth_source'] = 'actual Cycles Z converted with evaluated camera projection'
        for name in ('before.png', 'after.png', 'ngx_output.rgba8'):
            shutil.copyfile(job.work / name, out / name)
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        if job is not None:
            if job.process is not None and job.process.poll() is None:
                job.process.kill()
                job.process.wait(timeout=5)
            if job.log is not None:
                job.log.flush()
            for log in job.root.glob('*.log'):
                shutil.copyfile(log, out / log.name)
            job.close()
        (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
