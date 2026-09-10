"""Exercise the addon's FrameJob with downloaded, digest-verified CI fixtures."""
import hashlib
import importlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import types
import zipfile

root = Path(__file__).resolve().parents[1]
package = types.ModuleType('frame_test_addon')
package.__path__ = [str(root / 'addon/cycles_dlss5')]
sys.modules[package.__name__] = package
FrameJob = importlib.import_module('frame_test_addon.frame_job').FrameJob
out = Path(tempfile.mkdtemp(prefix='dlss5-gpu-test-'))
print('Evidence: ' + str(out), flush=True)
fixtures = (
    ('cycles-frame-input.zip', 'e127e9e65157411ac0806b8ed4b902a27d30ff3ae92204cc6a84a5957c5b758d', 'payload'),
    ('experimental-upstream-frame-host.zip', '8b7ddf1bff70e6b5503f65c496b45ddc6b2beec582dd3680e2de74d096de99ff', 'compiled'))
job = None
report = {'nr_confirmed': False}
try:
    for name, digest, target in fixtures:
        archive = Path(sys.argv[1]) / name
        if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
            raise ValueError('Archive digest mismatch: ' + name)
        with zipfile.ZipFile(archive) as z:
            destination = out / target
            for entry in z.infolist():
                if not (destination / entry.filename).resolve().is_relative_to(destination.resolve()):
                    raise ValueError('Unsafe archive member')
            z.extractall(destination)
    job = FrameJob(out / 'payload', out / 'compiled/host/dlss5-feed-host64.exe', sys.argv[2])
    job.start()
    while (code := job.poll()) is None:
        time.sleep(.2)
    report['exit_code'] = code
    report.update(job.finish(code))
except Exception as error:
    report['error'] = str(error)
finally:
    if job is not None:
        if job.process is not None and job.process.poll() is None:
            job.process.kill()
            job.process.wait(timeout=5)
        if job.log is not None:
            job.log.flush()
        for log in job.root.glob('*.log'):
            shutil.copyfile(log, out / log.name)
        for name in ('ngx_output.rgba8', 'before.png', 'after.png', 'verified-result.json'):
            if (job.work / name).exists():
                shutil.copyfile(job.work / name, out / name)
        job.close()
    (out / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)
sys.exit(0 if report['nr_confirmed'] else 1)
