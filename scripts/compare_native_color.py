"""Compare saved SDR backends without rerunning a GPU or changing Blender."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


def encode(frame):
    if frame.ndim != 3 or frame.shape[2] != 4 or not np.isfinite(frame).all():
        raise ValueError('Expected finite display-linear RGBA')
    value = np.clip(frame, 0, 1).copy()
    rgb = value[:, :, :3]
    value[:, :, :3] = np.where(rgb <= .0031308, rgb*12.92, 1.055*rgb**(1/2.4)-.055)
    return np.rint(value*255).astype(np.uint8)


def metrics(a, b):
    if a.shape != b.shape or a.ndim != 3 or a.shape[2] != 4:
        raise ValueError('Mismatched RGBA images')
    delta = np.abs(a[:, :, :3].astype(float)-b[:, :, :3].astype(float))
    return dict(mean=float(delta.mean()), p95=float(np.percentile(delta, 95)),
                maximum=float(delta.max()),
                pixels_over_8_percent=float((delta.max(axis=2)>8).mean()*100),
                alpha_identical=bool(np.array_equal(a[:, :, 3], b[:, :, 3])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('before', 'reference', 'native', 'output'):
        parser.add_argument('--'+key, required=True, type=Path)
    args = parser.parse_args()
    before = np.asarray(Image.open(args.before).convert('RGBA'))
    reference = np.asarray(Image.open(args.reference).convert('RGBA'))
    raw = np.load(args.native, allow_pickle=False)
    native = encode(raw)
    report = dict(native_vs_reference=metrics(native, reference),
                  native_vs_input=metrics(native, before), reference_vs_input=metrics(reference, before),
                  native_rgb_out_of_range=int(((raw[:, :, :3]<0)|(raw[:, :, :3]>1)).sum()),
                  quality_improvement_confirmed=False,
                  source_sha256={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in (args.before, args.reference, args.native)})
    args.output.mkdir(parents=True, exist_ok=False)
    Image.fromarray(native).save(args.output/'native.png')
    difference = np.abs(native[:, :, :3].astype(float)-reference[:, :, :3].astype(float))
    heat = np.clip(difference*8, 0, 255).astype(np.uint8)
    height, width = native.shape[:2]
    sheet = Image.new('RGB', (width*2, (height+28)*2), '#202020')
    draw = ImageDraw.Draw(sheet)
    for i, (label, array) in enumerate((('Input', before), ('RenoDX', reference),
                                       ('Native persistent', native), ('Absolute RGB difference x8', heat))):
        x, y = (i%2)*width, (i//2)*(height+28)
        draw.text((x+8, y+6), label, fill='white')
        sheet.paste(Image.fromarray(array).convert('RGB'), (x, y+28))
    sheet.save(args.output/'comparison.png')
    (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
