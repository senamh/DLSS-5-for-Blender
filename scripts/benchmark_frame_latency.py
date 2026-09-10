"""Measure NR stages on an existing official demo payload; no scene edits."""
import importlib
import json
from pathlib import Path
import sys
import time
import types

root = Path(__file__).resolve().parents[1]
package = types.ModuleType('_latency')
package.__path__ = [str(root / 'addon/cycles_dlss5')]
sys.modules[package.__name__] = package
FrameJob = importlib.import_module('_latency.frame_job').FrameJob
payload, runtime = map(Path, sys.argv[1:3])
job = None
try:
    for index in range(2):
        start = time.perf_counter()
        if job is not None and hasattr(job, 'prepare'):
            job.prepare(payload)
        else:
            if job is not None:
                job.close()
            job = FrameJob(payload, runtime / 'frame-host/dlss5-feed-host64.exe', runtime)
        prepared = time.perf_counter()
        job.start()
        while (code := job.poll()) is None:
            time.sleep(.05)
        executed = time.perf_counter()
        report = job.finish(code)
        end = time.perf_counter()
        print(json.dumps(dict(iteration=index, prepare=prepared-start, host=executed-prepared,
              verify=end-executed, total=end-start, nr=report['nr_confirmed'],
              size=report['size'], input_sha256=report['input_sha256'])), flush=True)
finally:
    if job is not None:
        job.close()
