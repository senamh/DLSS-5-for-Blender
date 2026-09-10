"""Use a packaged runtime from a new directory, without old PC paths."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import zipfile

archive, payload = map(Path, sys.argv[1:3])
with tempfile.TemporaryDirectory(prefix='dlss5-relocated-') as directory:
    root = Path(directory)
    with zipfile.ZipFile(archive) as bundle:
        # This test accepts our own allowlisted archive, never arbitrary extraction.
        for item in bundle.infolist():
            target = (root / item.filename).resolve()
            if not target.is_relative_to(root.resolve()):
                raise ValueError('Unsafe archive path')
        bundle.extractall(root)
    package = types.ModuleType('_relocated')
    package.__path__ = [str(root)]
    sys.modules[package.__name__] = package
    setup = importlib.import_module('_relocated.runtime_setup')
    FrameJob = importlib.import_module('_relocated.frame_job').FrameJob
    host, runtime = setup.resolve(addon=root, environ={}, system='win32')
    assert runtime == root / 'runtime'
    setup.verify_files(host, runtime)
    job = FrameJob(payload, host, runtime)
    try:
        job.start()
        while (code := job.poll()) is None:
            time.sleep(.1)
        report = job.finish(code, diagnostics=False)
        assert report['nr_confirmed']
        print('RELOCATED_RUNTIME_NR_OK', json.dumps({'size': report['size'],
              'input_sha256': report['input_sha256'], 'nr_confirmed': True}), flush=True)
    finally:
        job.close()
