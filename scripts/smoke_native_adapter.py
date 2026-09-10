"""Exercise the exact image-only adapter used by viewport and final render."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import time
import types
from PIL import Image

package = types.ModuleType('adapter_test')
package.__path__ = [str(Path(__file__).resolve().parents[1]/'addon/cycles_dlss5')]
sys.modules[package.__name__] = package
from adapter_test.native_frame_job import NativeFrameJob
from adapter_test.render_payload import prepare_image, publish_image

parser = argparse.ArgumentParser(description=__doc__)
for name in ('image', 'blender', 'bridge', 'runtime', 'output'):
    parser.add_argument('--'+name, required=True, type=Path)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
command = [str(args.blender), '--background', '--factory-startup', '--disable-autoexec',
           '--python-exit-code', '1', '--python']
image = Image.open(args.image).convert('RGBA')
reports = []
job = None
try:
    with tempfile.TemporaryDirectory() as folder:
        prepare_image(folder, image.tobytes(), *image.size)
        job = NativeFrameJob(folder, command, args.bridge, args.runtime)
        for i in range(2):
            if i:
                job.prepare(folder)
            job.start()
            while (code := job.poll()) is None:
                time.sleep(.01)
            report = job.finish(code, diagnostics=False)
            publish_image(job, report, args.output/f'frame-{i}.png')
            reports.append(report)
        assert reports[0]['pid'] == reports[1]['pid']
        assert (args.output/'frame-0.png').read_bytes() == (args.output/'frame-1.png').read_bytes()
finally:
    if job is not None:
        job.close()
(args.output/'report.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
print('Adapter passed: pinned private runtime, repeated frame, same PID, PNG publication and cleanup')
