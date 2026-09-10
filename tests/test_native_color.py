import importlib.util
from pathlib import Path
import unittest
import numpy as np

spec = importlib.util.spec_from_file_location('native_color_compare',
    Path(__file__).resolve().parents[1]/'scripts/compare_native_color.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ColorTests(unittest.TestCase):
    def test_srgb_roundtrip_all_bytes_and_alpha(self):
        srgb = np.arange(256, dtype=np.float32)/255
        linear = np.where(srgb <= .04045, srgb/12.92, ((srgb+.055)/1.055)**2.4)
        frame = np.stack([linear, linear, linear, srgb], axis=1)[None]
        expected = np.tile(np.arange(256, dtype=np.uint8)[None, :, None], (1, 1, 4))
        np.testing.assert_array_equal(module.encode(frame), expected)

    def test_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            module.encode(np.full((1, 1, 4), np.nan))

    def test_metrics_do_not_hide_alpha_difference(self):
        a = np.zeros((1, 1, 4), dtype=np.uint8)
        b = a.copy()
        b[:, :, 3] = 255
        result = module.metrics(a, b)
        self.assertEqual(result['mean'], 0)
        self.assertFalse(result['alpha_identical'])
