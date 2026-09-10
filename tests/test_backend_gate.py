import importlib
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

PACKAGE = '_cycles_gate_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'addon/cycles_dlss5')]
sys.modules[PACKAGE] = package
backend = importlib.import_module(PACKAGE + '.backend')


class BackendGateTests(unittest.TestCase):
    def exercise(self, receipt_error=None, color=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bridge = root / 'dlss5nr_bridge.dll'
            bridge.touch()
            (root / 'caller').mkdir()
            (root / 'caller/nvngx.dll_blender.dll').touch()
            report = types.SimpleNamespace(path=root / 'nvngx_dlssnr.dll', recognized=True)
            with patch.object(backend.sys, 'platform', 'win32'), \
                 patch.object(backend, 'validate_runtime', return_value=report), \
                 patch.object(backend, 'identity', return_value={'checked': True}), \
                 patch.object(backend, 'require_receipt', side_effect=receipt_error):
                return backend.configure(str(root), str(bridge), probe_report='report.json',
                                         allow_experimental_color=color)

    def tearDown(self):
        backend.restore_environment()

    def test_stale_receipt_never_changes_native_environment(self):
        before = dict(os.environ)
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.exercise(ValueError('stale'), color=True)
        self.assertEqual(dict(os.environ), before)

    def test_color_acknowledgement_is_required_after_probe(self):
        before = dict(os.environ)
        with self.assertRaisesRegex(ValueError, 'experimental color'):
            self.exercise(color=False)
        self.assertEqual(dict(os.environ), before)

    def test_success_sets_order_and_restores_previous_environment(self):
        before = dict(os.environ)
        self.exercise(color=True)
        self.assertEqual(os.environ['CYCLES_DLSS5NR_OUTPUT_ORDER'], 'RGB')
        backend.restore_environment()
        self.assertEqual(dict(os.environ), before)

