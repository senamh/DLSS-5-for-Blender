import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('depth_ablation',
    Path(__file__).resolve().parents[1] / 'scripts/compare_cycles_depth.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DepthAblationTests(unittest.TestCase):
    def test_metrics_ignore_alpha_but_full_equality_does_not(self):
        result = module.difference(bytes([0, 10, 20, 255]), bytes([0, 10, 20, 0]))
        self.assertEqual(result['changed_channels'], 0)
        self.assertFalse(result['identical_bytes'])

    def test_channel_differences(self):
        result = module.difference(bytes([0, 10, 20, 255]), bytes([3, 10, 26, 255]))
        self.assertEqual(result['mean_rgb_difference'], 3)
        self.assertEqual(result['max_rgb_difference'], 6)
        self.assertEqual(result['changed_channels'], 2)

    def test_reject_mismatched_buffers(self):
        with self.assertRaises(ValueError):
            module.difference(bytes(4), bytes(8))
