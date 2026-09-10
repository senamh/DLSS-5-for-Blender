"""Attributed official demos: real Cycles renders + unchanged-input NR style checks."""
import hashlib
import json
from pathlib import Path
import sys
import time
import tempfile
import bpy
import addon_utils

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'addon'))
addon_utils.enable('cycles_dlss5', default_set=True, persistent=True)
from cycles_dlss5 import final_render as final
from cycles_dlss5.styles import values

assets = Path(sys.argv[sys.argv.index('--') + 1])
manifest = json.loads((assets / 'SOURCES.json').read_text())
for demo in manifest['demos']:
    source = assets / demo['file']
    assert hashlib.sha256(source.read_bytes()).hexdigest() == demo['sha256']
    print('DEMO_START', demo['title'], flush=True)
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    scene.dlss5_style.final_enabled = False
    folder = Path(tempfile.mkdtemp(prefix=source.stem + '-results-', dir=assets))
    missing = [im.filepath for im in bpy.data.images if im.source == 'FILE' and not im.packed_file
               and im.filepath and not Path(bpy.path.abspath(im.filepath)).is_file()]
    if missing:
        raise RuntimeError('Missing demo textures: ' + repr(missing[:5]))
    original = dict(resolution=[scene.render.resolution_x, scene.render.resolution_y,
                                scene.render.resolution_percentage], engine=scene.render.engine,
                    samples=scene.cycles.samples, format=scene.render.image_settings.file_format)
    scene.render.resolution_percentage = min(scene.render.resolution_percentage,
              max(1, int(1024 * 100 / max(scene.render.resolution_x, scene.render.resolution_y))))
    if scene.render.engine == 'CYCLES':
        scene.cycles.samples = min(scene.cycles.samples, 32)
        scene.cycles.use_denoising = True
        scene.render.use_persistent_data = False
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        devices = [d for d in prefs.devices if d.type == 'OPTIX']
        if not devices:
            raise ValueError('No OptiX device for the official-scene benchmark')
        for device in prefs.devices:
            device.use = device.type == 'OPTIX'
        scene.cycles.device = 'GPU'
    scene.render.image_settings.media_type = 'IMAGE'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.color_depth = '8'
    scene.render.filepath = str(folder / 'render-')
    started = time.monotonic()
    bpy.ops.render.render()
    print('DEMO_RENDERED', demo['title'], time.monotonic() - started, flush=True)
    input_folder = folder / 'input'
    input_folder.mkdir()
    final.capture_render(scene, input_folder)
    reports = []
    for style in ('0', '1'):
        settings = scene.dlss5_style
        settings.style = style
        settings.intensity = settings.tone = settings.structure = 1
        settings.skin, settings.auto_mask = -1, False
        expected = values(settings)
        final.begin(scene, expected)
        limit = time.monotonic() + 65
        while final._active is not None and time.monotonic() < limit:
            final.poll_job()
            time.sleep(.1)
        if final._active is not None or not final.has_result():
            raise RuntimeError(final.prefs().final_status)
        report = json.loads(final._last_image['dlss5_report'])
        assert report['settings'] == expected
        if reports:
            assert report['input_sha256'] == reports[0]['input_sha256']
        path = folder / ('DLSS-Default.png' if style == '0' else 'DLSS-Natural.png')
        path.write_bytes(final._last_image.packed_file.data)
        reports.append(report)
        print('DEMO_NR', demo['title'], style, report['mean_absolute_rgb_difference_8bit'], flush=True)
    (folder / 'report.json').write_text(json.dumps({'source': demo, 'original_settings': original,
        'test_settings': {'resolution_percentage': scene.render.resolution_percentage, 'samples': scene.cycles.samples},
        'reports': reports, 'quality_improvement_confirmed': False}, indent=2))
    assert hashlib.sha256(source.read_bytes()).hexdigest() == demo['sha256'], 'Original demo was changed'
    print('DEMO_OK', demo['title'], folder, flush=True)
