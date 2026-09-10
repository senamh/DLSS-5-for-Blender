"""Create exact-camera PNG comparisons using both actual addon backends."""
import argparse
import importlib
import json
from pathlib import Path
import sys
import tempfile
import time
import types
from PIL import Image, ImageDraw
import numpy as np

package = types.ModuleType('quality_addon')
package.__path__ = [str(Path(__file__).resolve().parents[1]/'addon/cycles_dlss5')]
sys.modules[package.__name__] = package
from quality_addon.frame_job import FrameJob
from quality_addon.native_frame_job import NativeFrameJob
from quality_addon.render_payload import prepare_image, publish_image
from quality_addon.runtime_setup import resolve, verify_files
from quality_addon.style_config import PRESETS, FIELDS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('folder', 'blender', 'bridge', 'runtime'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--preset', choices=PRESETS, default='BALANCED')
    parser.add_argument('--style', choices=('0', '1'), default='0', help='0 Default, 1 Natural')
    args = parser.parse_args()
    original = Image.open(args.folder/'01-original.png').convert('RGBA')
    settings = dict(zip(FIELDS, PRESETS[args.preset]))
    settings['style'] = int(args.style)
    reports = {}
    command = [str(args.blender), '--background', '--factory-startup', '--disable-autoexec',
               '--python-exit-code', '1', '--python']
    host, runtime = resolve()
    verify_files(host, runtime)
    with tempfile.TemporaryDirectory() as payload:
        prepare_image(payload, original.tobytes(), *original.size)
        for label, make in (
            ('02-DLSS5-RenoDX', lambda: FrameJob(payload, host, runtime, settings)),
            ('03-DLSS5-Native', lambda: NativeFrameJob(payload, command, args.bridge, args.runtime, settings))):
            if args.preset != 'BALANCED':
                label += '-'+args.preset
            if args.style == '1':
                label += '-Natural'
            job = make()
            try:
                start = time.monotonic()
                job.start()
                while (code := job.poll()) is None:
                    time.sleep(.05)
                report = job.finish(code, diagnostics=False)
                report['processing_seconds'] = time.monotonic()-start
                report['settings'] = settings
                publish_image(job, report, args.folder/(label+'.png'))
                processed = Image.open(args.folder/(label+'.png')).convert('RGBA')
                assert processed.size == original.size
                assert processed.getchannel('A').tobytes() == original.getchannel('A').tobytes()
                a, b = np.asarray(original), np.asarray(processed)
                delta = np.abs(a[:, :, :3].astype(float)-b[:, :, :3].astype(float))
                report['difference_not_quality'] = dict(mean=float(delta.mean()), p95=float(np.percentile(delta,95)))
                reports[label] = report
                w, h = original.size
                sheet = Image.new('RGB', (w*2, h+40), '#202020')
                draw = ImageDraw.Draw(sheet)
                draw.text((12, 12), 'Original Cycles | same camera, same source frame', fill='white')
                draw.text((w+12, 12), label+' | '+args.preset+' | SDR', fill='white')
                sheet.paste(original.convert('RGB'), (0,40))
                sheet.paste(processed.convert('RGB'), (w,40))
                sheet.save(args.folder/('Compare-'+label+'.png'))
                # Unscaled, matched center crop for inspecting fine detail.
                cw, ch = min(720,w), min(720,h)
                box = ((w-cw)//2, (h-ch)//2, (w+cw)//2, (h+ch)//2)
                crops = Image.new('RGB', (cw*2,ch+40), '#202020')
                dc = ImageDraw.Draw(crops)
                dc.text((12,12), 'Original - center crop 1:1', fill='white')
                dc.text((cw+12,12), label+' - center crop 1:1', fill='white')
                crops.paste(original.crop(box).convert('RGB'), (0,40))
                crops.paste(processed.crop(box).convert('RGB'), (cw,40))
                crops.save(args.folder/('Detail-'+label+'.png'))
            finally:
                job.close()
    report_name = 'NR-report.json' if args.preset == 'BALANCED' else 'NR-report-'+args.preset+'.json'
    if args.style == '1':
        report_name = report_name.replace('.json', '-Natural.json')
    (args.folder/report_name).write_text(json.dumps(reports, indent=2), encoding='utf-8')
    print('QUALITY_PAIRS_OK', args.folder, flush=True)


if __name__ == '__main__':
    main()
