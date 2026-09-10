"""Disposable background Cycles test. Requires a passing runtime probe receipt."""
import argparse
import importlib
import json
import math
from pathlib import Path
import sys
import time
import types

import bpy
import _cycles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True)
    parser.add_argument('--bridge', required=True)
    parser.add_argument('--probe-report', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--order', choices=['RGB', 'BGR'], default='RGB')
    parser.add_argument('--trust-runtime', action='store_true')
    parser.add_argument('--allow-experimental-color', action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
    if not bpy.app.background:
        raise RuntimeError('Use --background --factory-startup; this test creates its own scene')
    if not args.trust_runtime or not args.allow_experimental_color:
        raise RuntimeError('Review the probe images and pass both explicit opt-in flags')
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {'passed': False, 'scope': 'two independent Cycles frames; no viewport/FPS/HDR certification'}
    try:
        if not getattr(_cycles, 'with_dlss5nr', False):
            raise RuntimeError('This Blender has no compiled DLSS5NR backend')
        # Import validation without registering UI or loading a native DLL here.
        source = Path(__file__).resolve().parents[1] / 'addon' / 'cycles_dlss5'
        if not source.is_dir():
            source = Path(bpy.app.binary_path).parent / 'dlss5-addon' / 'cycles_dlss5'
        package = types.ModuleType('_dlss5_acceptance')
        package.__path__ = [str(source)]
        sys.modules[package.__name__] = package
        backend = importlib.import_module(package.__name__ + '.backend')
        runtime = backend.configure(args.runtime, args.bridge, True, args.probe_report,
                                    args.order, True)
        report['runtime_sha256'] = runtime.sha256
        report['blender'] = bpy.app.version_string
        preferences = bpy.context.preferences.addons['cycles'].preferences
        preferences.compute_device_type = 'OPTIX'
        preferences.get_devices()
        devices = [device for device in preferences.devices if device.type == 'OPTIX']
        if len(devices) != 1:
            raise RuntimeError('This test requires exactly one OptiX GPU; CPU fallback is refused')
        for device in preferences.devices:
            device.use = device in devices
        report['optix_gpu'] = devices[0].name

        scene = bpy.data.scenes.new('DLSS5 acceptance')
        bpy.context.window.scene = scene
        scene.render.engine = 'CYCLES'
        scene.cycles.device = 'GPU'
        scene.cycles.samples = 32
        scene.cycles.use_adaptive_sampling = False
        scene.cycles.seed = 17
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = True
        scene.render.image_settings.file_format = 'OPEN_EXR'
        scene.render.image_settings.color_mode = 'RGBA'
        scene.render.image_settings.color_depth = '32'
        camera = bpy.data.objects.new('Camera', bpy.data.cameras.new('Camera'))
        scene.collection.objects.link(camera)
        camera.location = (0, 0, 6)
        scene.camera = camera
        mesh = bpy.data.meshes.new('Chart')
        mesh.from_pydata([(-1.5, -1, 0), (1.5, -1, 0), (1.5, 1, 0), (-1.5, 1, 0)], [], [(0, 1, 2, 3)])
        obj = bpy.data.objects.new('Chart', mesh)
        scene.collection.objects.link(obj)
        material = bpy.data.materials.new('HDR emission')
        material.use_nodes = True
        nodes = material.node_tree.nodes
        nodes.clear()
        emission = nodes.new('ShaderNodeEmission')
        emission.inputs['Color'].default_value = (0.8, 0.2, 0.05, 1)
        emission.inputs['Strength'].default_value = 4
        out = nodes.new('ShaderNodeOutputMaterial')
        material.node_tree.links.new(emission.outputs[0], out.inputs['Surface'])
        mesh.materials.append(material)

        def render(name, enabled):
            scene.cycles.use_denoising = enabled
            if enabled:
                scene.cycles.denoiser = 'DLSS5NR'
                if scene.cycles.denoiser != 'DLSS5NR':
                    raise RuntimeError('DLSS enum selection failed')
            path = output / (name + '.exr')
            scene.render.filepath = str(path)
            start = time.perf_counter()
            bpy.ops.render.render(write_still=True, scene=scene.name)
            elapsed = time.perf_counter() - start
            image = bpy.data.images.load(str(path), check_existing=False)
            try:
                pixels = list(image.pixels[:])
                if len(pixels) != scene.render.resolution_x * scene.render.resolution_y * 4:
                    raise RuntimeError('Unexpected EXR pixel count')
                if not all(math.isfinite(value) for value in pixels):
                    raise RuntimeError('Non-finite EXR pixels')
                return pixels, elapsed
            finally:
                bpy.data.images.remove(image)

        report['frames'] = []
        for frame, width in ((1, 256), (2, 320)):
            scene.frame_set(frame)
            scene.render.resolution_x = width
            scene.render.resolution_y = 256
            obj.location.x = 0 if frame == 1 else 0.3
            raw, raw_time = render(f'{frame}-cycles', False)
            enhanced, nr_time = render(f'{frame}-dlss5', True)
            alpha_error = max(abs(a - b) for a, b in zip(raw[3::4], enhanced[3::4]))
            rgb_indices = [i for i in range(len(raw)) if i % 4 != 3]
            change = sum(abs(raw[i] - enhanced[i]) for i in rgb_indices) / len(rgb_indices)
            if alpha_error > 1e-5:
                raise RuntimeError(f'Alpha changed: {alpha_error}')
            if change <= 1e-5:
                raise RuntimeError('No measurable DLSS effect; EXRs need investigation')
            report['frames'].append({'frame': frame, 'width': width,
                'cycles_seconds': raw_time, 'dlss5_seconds': nr_time,
                'rgb_mean_change': change, 'alpha_max_error': alpha_error,
                'input_rgb_max': max(raw[i] for i in rgb_indices),
                'output_rgb_max': max(enhanced[i] for i in rgb_indices)})
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        (output / 'cycles-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

