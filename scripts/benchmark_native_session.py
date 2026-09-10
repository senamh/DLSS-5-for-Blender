"""Run A/A/B/A/zero/A in one native session; no installed addon changes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'frames': [], 'temporal_accumulation': False, 'quality_improvement_confirmed': False,
              'binary_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                  (args.bridge, args.runtime / 'nvngx_dlssnr.dll',
                   args.runtime / 'caller/nvngx.dll_blender.dll')}}
    source = Path(__file__).resolve().parents[1] / 'addon/cycles_dlss5/stock_worker.py'
    spec = importlib.util.spec_from_file_location('session_worker', source)
    worker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(worker)
    image = np.asarray(Image.open(args.image).convert('RGBA'), dtype=np.float32) / 255
    linear = image.copy()
    linear[:, :, :3] = np.where(image[:, :, :3] <= .04045, image[:, :, :3] / 12.92,
                                ((image[:, :, :3] + .055) / 1.055) ** 2.4)
    results = []
    try:
        for index, (kind, intensity) in enumerate((('A', 1), ('A', 1), ('B', 1),
                                                  ('A', 1), ('A', 0), ('A', 1))):
            frame = linear.copy()
            if kind == 'B':
                frame[:, :, :3] = frame[:, :, :3][:, ::-1]
            np.save(args.output / 'input.npy', frame, allow_pickle=False)
            job = dict(bridge=str(args.bridge), runtime=str(args.runtime), order='RGB',
                       color_mode='DISPLAY_LINEAR', input=str(args.output / 'input.npy'),
                       output=str(args.output / f'output-{index}.npy'), settings={
                       'style': '0', 'intensity': intensity, 'tone': 1, 'structure': 1,
                       'skin': -1, 'auto_mask': False})
            path = args.output / 'job.json'
            path.write_text(json.dumps(job))
            started = time.monotonic()
            info = worker.process(path)
            info.update(seconds=time.monotonic()-started, frame=kind, intensity=intensity)
            result = np.load(job['output'], allow_pickle=False)
            assert np.array_equal(result[:, :, 3], frame[:, :, 3])
            results.append(result)
            info['output_sha256'] = hashlib.sha256(result.tobytes()).hexdigest()
            report['frames'].append(info)
            print(index, info, flush=True)
        report['repeat_identical'] = bool(np.array_equal(results[0], results[1]))
        report['after_other_frame_identical'] = bool(np.array_equal(results[0], results[3]))
        report['after_settings_change_identical'] = bool(np.array_equal(results[0], results[5]))
        report['intensity_changes_result'] = bool(not np.array_equal(results[0], results[4]))
        assert all(report[k] for k in ('repeat_identical', 'after_other_frame_identical',
                                      'after_settings_change_identical', 'intensity_changes_result'))
    finally:
        if worker._dll is not None:
            worker._dll.dlss5nr_shutdown()
        (args.output / 'report.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
