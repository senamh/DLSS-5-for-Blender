"""Behavioral tests for the probe's rejection rules, with no native DLL execution."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'addon/cycles_dlss5/probe.py'
SPEC = importlib.util.spec_from_file_location('probe_under_test', PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def test_passthrough_is_not_proof_of_neural_execution(self):
        source = probe.chart()
        with self.assertRaisesRegex(ValueError, 'No measurable'):
            probe.stats(source, source)

    def test_correct_channels_with_change_pass(self):
        source = probe.chart()
        result = [x * 0.9 for x in source]
        self.assertGreater(probe.stats(source, result)['mean_absolute_change'], 0)

    def test_swapped_red_blue_fails(self):
        source = probe.chart()
        result = [source[i + c] * 0.9 for i in range(0, len(source), 3) for c in (2, 1, 0)]
        with self.assertRaisesRegex(ValueError, 'Color chart'):
            probe.stats(source, result)

    def test_partial_output_nan_fails(self):
        source = probe.chart()
        result = [x * 0.9 for x in source]
        result[-1] = float('nan')
        with self.assertRaisesRegex(ValueError, 'invalid pixels'):
            probe.stats(source, result)

    def test_receipt_rejects_failed_stale_and_malformed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'report.json'
            expected = {'hashes': {'runtime': 'current'}, 'devices': ['4070, uuid, driver']}
            for data in (
                {'schema': probe.SCHEMA, 'passed': False, 'identity': expected},
                {'schema': probe.SCHEMA, 'passed': True, 'identity': {'old': True}},
                [],
            ):
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    probe.require_receipt(path, expected)
            path.write_text('{')
            with self.assertRaises(ValueError):
                probe.require_receipt(path, expected)
            path.write_text(json.dumps({'schema': probe.SCHEMA, 'passed': True, 'identity': expected}))
            self.assertTrue(probe.require_receipt(path, expected)['passed'])

    def test_identity_changes_when_native_file_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'caller').mkdir()
            for path in (root / 'nvngx_dlssnr.dll', root / 'dlss5nr_bridge.dll',
                         root / 'caller/nvngx.dll_blender.dll'):
                path.write_bytes(b'initial bytes')
            with patch.object(probe.subprocess, 'run') as run:
                run.return_value.stdout = 'NVIDIA GeForce RTX 4070, GPU-test, 123.45\n'
                before = probe.identity(root, root / 'dlss5nr_bridge.dll', 'RGB')
                (root / 'dlss5nr_bridge.dll').write_bytes(b'changed bytes')
                after = probe.identity(root, root / 'dlss5nr_bridge.dll', 'RGB')
                self.assertNotEqual(before, after)
                run.return_value.stdout += 'Another NVIDIA GPU, GPU-other, 123.45\n'
                with self.assertRaisesRegex(ValueError, 'one NVIDIA GPU'):
                    probe.identity(root, root / 'dlss5nr_bridge.dll', 'RGB')

