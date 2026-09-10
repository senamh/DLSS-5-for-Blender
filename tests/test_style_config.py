import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('style_config', ROOT / 'addon/cycles_dlss5/style_config.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class StyleConfigTests(unittest.TestCase):
    def setUp(self):
        self.values = dict(zip(module.FIELDS, module.PRESETS['BALANCED']))

    def test_presets_map_to_native_controls(self):
        for preset in module.PRESETS.values():
            mapped = module.native_values(dict(zip(module.FIELDS, preset)))
            self.assertEqual(set(mapped), set(module.KEYS))
            self.assertEqual(mapped['NRStyle'], '0')

    def test_baseline_matches_official_demo_run(self):
        self.assertEqual(module.PRESETS['BALANCED'], (0, 1., 1., 1., -1., False))

    def test_reject_invalid_values(self):
        for field, value in (('style', 2), ('intensity', float('nan')),
                             ('tone', float('inf')), ('structure', -1),
                             ('skin', -2), ('intensity', 2.01), ('auto_mask', '0')):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                module.native_values({**self.values, field: value})

    def test_profile_isolated_and_preserves_input(self):
        with tempfile.TemporaryDirectory() as directory:
            # CI uses RUNNER~1 while resolve() expands it to runneradmin.
            root = Path(directory).resolve()
            runtime = root / 'runtime'
            folder = root / 'session'
            runtime.mkdir()
            folder.mkdir()
            original = ('[RenoDX.DLSS5]\nNRStyle=2\nNRIntensity=2\n'
                        '[INPUT]\nKeyOverlay=119,0,0,0\n'
                        '[GENERAL]\nEffectSearchPaths=shaders/**\n'
                        '[SCREENSHOT]\nFileNaming=present-%Count%\nPostSaveCommand=old-command\n')
            (runtime / 'ReShade.ini').write_text(original)
            (runtime / 'ReShadePreset.ini').write_text('Techniques=DLSS5')
            (runtime / 'opengl32.dll').write_bytes('RESHADE_BASE_PATH_OVERRIDE'.encode('utf-16-le'))
            module.prepare_profile(runtime, folder, self.values)
            self.assertEqual((runtime / 'ReShade.ini').read_text(), original)
            config = module.parse_ini((folder / 'ReShade.ini').read_text())
            self.assertEqual(config['RenoDX.DLSS5']['NRStyle'], '0')
            self.assertEqual(config['RenoDX.DLSS5']['NRIntensity'], '1.000000')
            self.assertEqual(config['INPUT']['KeyOverlay'], '119,0,0,0')
            self.assertEqual(config['SCREENSHOT']['FileNaming'], 'present-%Count%')
            self.assertEqual(config['SCREENSHOT']['PostSaveCommand'], '')
            self.assertEqual(Path(config['GENERAL']['EffectSearchPaths']), runtime / 'shaders/**')
            self.assertEqual(Path(config['GENERAL']['PresetPath']), folder / 'ReShadePreset.ini')
            self.assertEqual((folder / 'ReShadePreset.ini').read_text(), 'Techniques=DLSS5')
            self.assertTrue((folder / 'Screenshots').is_dir())

    def test_reject_install_base_path_override(self):
        with self.assertRaises(ValueError):
            module.build_config('[INSTALL]\nBasePath=somewhere', ROOT, ROOT, self.values)

    def test_reject_old_reshade(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'opengl32.dll').write_bytes(b'unsupported')
            with self.assertRaises(ValueError):
                module.prepare_profile(root, root, self.values)


if __name__ == '__main__':
    unittest.main()
