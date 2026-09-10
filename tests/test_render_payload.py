import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest

package = types.ModuleType('_render_tests')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'addon/cycles_dlss5')]
sys.modules[package.__name__] = package
module = importlib.import_module('_render_tests.render_payload')
gate = importlib.import_module('_render_tests.frame_result')


class RenderPayloadTests(unittest.TestCase):
    def test_comparison_preserves_complete_frames_and_alpha(self):
        source = bytes(range(32))
        processed = bytes(range(100, 132))
        result = module.comparison_rgba(source, processed, 2, 4)
        self.assertEqual(len(result), 64)
        for row in range(4):
            self.assertEqual(result[row * 16:row * 16 + 8], source[row * 8:row * 8 + 8])
            self.assertEqual(result[row * 16 + 8:row * 16 + 16], processed[row * 8:row * 8 + 8])
        with self.assertRaises(ValueError):
            module.comparison_rgba(source, processed[:-1], 2, 4)

    def test_image_payload_is_explicit_not_fake_cycles_guides(self):
        with tempfile.TemporaryDirectory() as directory:
            rgba = bytes([20, 40, 80, 127]) * (96 * 96)
            root = Path(directory)
            module.prepare_image(root, rgba, 96, 96)
            meta = gate.validate_payload(root)
            self.assertIn('no Cycles guides', meta['guides'])
            self.assertEqual((root / 'motion.f16').read_bytes(), bytes(96 * 96 * 4))
            (root / 'ngx_output.rgba8').write_bytes(bytes([30, 50, 90, 255]) * (96 * 96))
            report = {}
            module.publish_image(types.SimpleNamespace(work=root, meta=meta), report, root / 'final.png')
            self.assertTrue(report['alpha_preserved'])
            expected = bytearray([30, 50, 90, 127]) * (96 * 96)
            import hashlib
            self.assertEqual(report['published_rgba_sha256'], hashlib.sha256(expected).hexdigest())

    def test_reject_dimensions_and_bad_color(self):
        with tempfile.TemporaryDirectory() as root:
            for w, h, data in ((95, 96, b''), (4097, 96, b''), (96, 96, b'bad')):
                with self.assertRaises(ValueError):
                    module.prepare_image(root, data, w, h)
