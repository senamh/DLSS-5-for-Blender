import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('preview_controls', ROOT / 'addon/cycles_dlss5/preview_controls.py')
controls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controls)


class PreviewControlsTests(unittest.TestCase):
    def test_migration_preserves_effects_and_other_settings(self):
        ini = '[INPUT]\nKeyReload=118,0,0,0\nKeyScreenshot=117,0,0,0\nKeyFPS=0\n[OTHER]\nKeyReload=123\n'
        preset = ('KeyDLSS5_Feed@DLSS5_Feed.fx=121,0,0,0\nTechniques=A,DLSS5_Feed@DLSS5_Feed.fx\n'
                  '[DLSS5_Feed.fx]\nMASK_STRENGTH=0.7\n')
        new_ini, new_preset = controls.migrate_bindings(ini, preset)
        self.assertIn('KeyReload=134,0,0,0', new_ini)
        self.assertIn('KeyScreenshot=133,0,0,0', new_ini)
        self.assertIn('KeyOverlay=119,0,0,0', new_ini)
        self.assertIn('[OTHER]\nKeyReload=123', new_ini)
        self.assertIn('KeyDLSS5_Feed@DLSS5_Feed.fx=135,0,0,0', new_preset)
        self.assertIn('Techniques=A,DLSS5_Feed@DLSS5_Feed.fx', new_preset)
        self.assertIn('MASK_STRENGTH=0.7', new_preset)
        self.assertEqual(controls.migrate_bindings(new_ini, new_preset), (new_ini, new_preset))

    def test_adds_missing_bindings_and_removes_duplicate_key(self):
        ini, preset = controls.migrate_bindings('[OTHER]\nx=1\n',
            'KeyDLSS5_Feed@DLSS5_Feed.fx=121\nKeyDLSS5_Feed@DLSS5_Feed.fx=121\n')
        self.assertIn('[INPUT]', ini)
        self.assertEqual(preset.count('KeyDLSS5_Feed@DLSS5_Feed.fx='), 1)

    def test_buttons_use_actions_not_old_keycodes(self):
        source = (ROOT / 'addon/cycles_dlss5/preview_launch.py').read_text(encoding='utf-8')
        self.assertNotIn('dlss5.upstream_key', source)
        for action in controls.ACTION_KEYS:
            self.assertIn(".action = '" + action + "'", source)
        self.assertFalse({117,118,121} & set(controls.ACTION_KEYS.values()))
