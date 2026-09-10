import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('preview_state', Path(__file__).resolve().parents[1] / 'addon/cycles_dlss5/preview_state.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PreviewStateTests(unittest.TestCase):
    def test_notifications_or_style_do_not_hide_completed_image(self):
        key = ((1,), (2,), (0, 0, 128, 96), 1, ('style',), 'AgX', 'None', 0, 1, 'RENDERED', 0)
        updated = (*key[:-1], 1000)
        self.assertTrue(module.same_view(key, updated))
        updated = list(key)
        updated[4] = ('different style',)
        self.assertTrue(module.same_view(key, tuple(updated)))
        for index in (0, 1, 2, 3, 9):
            updated = list(key)
            updated[index] = 'changed'
            self.assertFalse(module.same_view(key, tuple(updated)))

    def test_float_noise_is_not_camera_movement(self):
        self.assertEqual(module.matrix_key([[1.000000001]]), module.matrix_key([[1.0]]))
        self.assertNotEqual(module.matrix_key([[1.0001]]), module.matrix_key([[1.0]]))
