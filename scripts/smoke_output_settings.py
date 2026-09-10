"""Test actual Blender encoders, file destinations and safe overwrite behavior."""
import json
from pathlib import Path
import sys
import tempfile
import bpy
import addon_utils
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'addon'))
addon_utils.enable('cycles_dlss5', default_set=True)
from cycles_dlss5 import output
from cycles_dlss5.frame_result import write_rgba_png
folder = Path(tempfile.mkdtemp(prefix='dlss5-output-test-'))
print('OUTPUT_TEST_EVIDENCE', folder, flush=True)
scene = bpy.context.scene
scene.view_settings.exposure = 1.25
scene.render.image_settings.file_format = 'PNG'
source = np.zeros((96, 128, 4), dtype=np.uint8)
source[:, :, 0] = np.arange(128) * 2
source[:, :, 1] = np.arange(96)[:, None] * 2
source[:, :, 2] = 64
source[:, :, 3] = np.arange(128) * 2
write_rgba_png(folder / 'source.png', source.tobytes(), 128, 96)
image = bpy.data.images.load(str(folder / 'source.png'), check_existing=False)
image.colorspace_settings.name = 'sRGB'
image.use_view_as_render = False
image.pack()
before = (scene.view_settings.exposure, scene.view_settings.view_transform, len(bpy.data.scenes))
assert bpy.ops.cycles_dlss5.output_folder(directory=str(folder)) == {'FINISHED'}
assert Path(scene.render.filepath).parent == folder
results = {}
for fmt in ('PNG', 'JPEG', 'TIFF', 'BMP', 'TARGA', 'TARGA_RAW', 'WEBP'):
    scene.render.image_settings.file_format = fmt
    if fmt in {'PNG', 'TIFF', 'TARGA', 'TARGA_RAW', 'WEBP'}:
        scene.render.image_settings.color_mode = 'RGBA'
    else:
        scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    config = output.snapshot(scene, 'BOTH')
    path = folder / (fmt + scene.render.file_extension)
    output.save(image, config, path)
    check = bpy.data.images.load(str(path), check_existing=False)
    assert tuple(check.size) == (128, 96)
    check.colorspace_settings.name = 'Non-Color'
    pixels = np.empty(128 * 96 * 4, dtype=np.float32)
    check.pixels.foreach_get(pixels)
    pixels = np.rint(pixels.reshape(96, 128, 4)[::-1] * 255).astype(np.uint8)
    expected = source[:, :, :3].astype(int)
    if config['color_mode'] == 'RGB':
        # Blender composites transparent pixels over black for alpha-less output.
        expected = np.rint(expected * source[:, :, 3:4] / 255).astype(int)
    delta = np.abs(pixels[:, :, :3].astype(int) - expected).max()
    if fmt in {'PNG', 'TIFF', 'BMP', 'TARGA', 'TARGA_RAW'}:
        assert delta <= 1, (fmt, delta, pixels[40, 40], source[40, 40])
    if config['color_mode'] == 'RGBA':
        assert np.array_equal(pixels[:, :, 3], source[:, :, 3]), fmt
    saved = path.read_bytes()
    try:
        output.save(image, config, path)
        raise AssertionError('Existing file was overwritten')
    except FileExistsError:
        assert path.read_bytes() == saved
    results[fmt] = {'max_rgb_difference_8bit': int(delta), 'size': len(saved)}
    bpy.data.images.remove(check)
    assert (scene.view_settings.exposure, scene.view_settings.view_transform, len(bpy.data.scenes)) == before
for fmt in ('PNG', 'TIFF'):
    scene.render.image_settings.file_format = fmt
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '16'
    path = folder / (fmt + '-16' + scene.render.file_extension)
    output.save(image, output.snapshot(scene), path)
    if fmt == 'PNG':
        assert path.read_bytes()[24] == 16, 'PNG was not encoded at selected 16-bit depth'
    check = bpy.data.images.load(str(path), check_existing=False)
    assert tuple(check.size) == (128, 96)
    bpy.data.images.remove(check)
scene.render.image_settings.file_format = 'PNG'
scene.render.use_file_extension = False
scene.render.filepath = str(folder / 'without-extension-####')
config = output.snapshot(scene, 'DISK')
assert config['path'].endswith('without-extension-0001')
output.save(image, config)
assert Path(config['path']).read_bytes().startswith(b'\x89PNG')
scene.render.use_file_extension = True
scene.render.image_settings.file_format = 'TIFF'
config = output.snapshot(scene, 'BOTH')
scene.render.image_settings.file_format = 'JPEG'
scene.render.filepath = str(folder / 'changed-in-flight-')
output.save(image, config)
assert Path(config['path']).suffix == '.tif'
scene.render.image_settings.file_format = 'OPEN_EXR'
try:
    output.snapshot(scene)
    raise AssertionError('HDR silently downgraded')
except ValueError:
    pass
(folder / 'report.json').write_text(json.dumps(results, indent=2))
print('OUTPUT_SETTINGS_OK', json.dumps(results), flush=True)
