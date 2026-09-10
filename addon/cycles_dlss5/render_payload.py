"""Single-image NR payload. Deliberately not labelled as real Cycles guides."""
import hashlib
import json
from pathlib import Path
from .frame_result import write_rgba_png


def prepare_image(root, rgba, width, height):
    root = Path(root)
    if not (96 <= width <= 4096 and 96 <= height <= 4096):
        raise ValueError('Финальная обработка поддерживает размеры от 96 до 4096 пикселей по каждой стороне')
    if len(rgba) != width * height * 4:
        raise ValueError('Неверный размер входного изображения')
    # Image postprocessing has no trusted depth/motion after the compositor.
    # Explicit neutral placeholders and reset history; never fabricate Cycles guides.
    arrays = {'color.rgba8': rgba, 'depth.f32': b'\x00\x00\x80\x3f' * (width * height),
              'motion.f16': bytes(width * height * 4)}
    files = {}
    for name, data in arrays.items():
        (root / name).write_bytes(data)
        files[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    meta = {'schema': 1, 'size': [width, height], 'origin': 'top-left', 'reset': True,
            'files': files, 'guides': 'image-only: constant far depth and zero motion; no Cycles guides',
            'color': 'Blender display-referred sRGB RGBA8'}
    (root / 'payload.json').write_text(json.dumps(meta, indent=2))
    return meta


def publish_image(job, report, destination):
    """Retain the original render alpha instead of trusting neural alpha output."""
    destination = Path(destination)
    source = (job.work / 'color.rgba8').read_bytes()
    data = bytearray((job.work / 'ngx_output.rgba8').read_bytes())
    data[3::4] = source[3::4]
    width, height = job.meta['size']
    write_rgba_png(destination, data, width, height)
    report['alpha_preserved'] = True
    report['published_rgba_sha256'] = hashlib.sha256(data).hexdigest()
    report['guides'] = job.meta.get('guides', 'unspecified')
    return report


def comparison_rgba(source, processed, width, height):
    """Two complete frames, original left / published DLSS right. No grading."""
    if len(source) != width * height * 4 or len(processed) != len(source):
        raise ValueError('Wrong comparison RGBA size')
    stride = width * 4
    data = bytearray(len(source) * 2)
    for y in range(height):
        start = y * stride
        data[start * 2:start * 2 + stride] = source[start:start + stride]
        data[start * 2 + stride:(start + stride) * 2] = processed[start:start + stride]
    return data
