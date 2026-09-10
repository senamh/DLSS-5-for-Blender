"""Reject well-hashed but unsafe guides before starting the GPU host."""
import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest

package = types.ModuleType('_guide_tests')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'addon/cycles_dlss5')]
sys.modules[package.__name__] = package
payload = importlib.import_module('_guide_tests.render_payload')
gate = importlib.import_module('_guide_tests.frame_result')


class GuidePayloadTests(unittest.TestCase):
    def check_guide(self, name, value, accepted):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload.prepare_image(root, bytes([32, 64, 96, 255]) * 96 * 96, 96, 96)
            data = bytearray((root / name).read_bytes())
            data[:len(value)] = value
            (root / name).write_bytes(data)
            meta = json.loads((root / 'payload.json').read_text())
            meta['files'][name]['sha256'] = hashlib.sha256(data).hexdigest()
            (root / 'payload.json').write_text(json.dumps(meta))
            if accepted:
                gate.validate_payload(root)
            else:
                with self.assertRaises(ValueError):
                    gate.validate_payload(root)

    def test_device_depth_boundaries(self):
        for value in (0., .5, 1.):
            self.check_guide('depth.f32', struct.pack('<f', value), True)

    def test_invalid_depth_with_valid_checksum(self):
        for value in (float('nan'), float('inf'), -.01, 1.01):
            self.check_guide('depth.f32', struct.pack('<f', value), False)

    def test_motion_rejected_until_temporal_contract_is_validated(self):
        self.check_guide('motion.f16', struct.pack('<ee', 1., 0.), False)
