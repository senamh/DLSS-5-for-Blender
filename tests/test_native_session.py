import hashlib
import importlib
import json
from pathlib import Path
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import Mock

import numpy as np

package = types.ModuleType('native_session_tests')
package.__path__ = [str(Path(__file__).resolve().parents[1]/'addon/cycles_dlss5')]
sys.modules[package.__name__] = package
NativeSession = importlib.import_module(package.__name__+'.native_session').NativeSession


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.session = s = NativeSession.__new__(NativeSession)
        s.root = Path(self.folder.name)
        s.process = Mock(pid=123)
        s.process.poll.return_value = None
        s.close = Mock()
        s.sequence = 1
        s.timeout = 60
        self.frame = np.ones((96, 96, 4), dtype=np.float32)
        s.pending = dict(frame=self.frame, settings={}, started=time.monotonic())
        digest = hashlib.sha256(self.frame.tobytes()).hexdigest()
        self.receipt = dict(sequence=1, pid=123, native_settings={}, reset=True,
                            temporal_accumulation=False, input_sha256=digest, output_sha256=digest)
        np.save(s.root/'output.npy', self.frame)
        (s.root/'request-1.json').write_text('{}')

    def publish(self):
        (self.session.root/'done-1.json').write_text(json.dumps(self.receipt))

    def test_matching_receipt_is_consumed_once(self):
        self.publish()
        self.assertTrue(np.array_equal(self.session.poll()[0], self.frame))
        self.assertIsNone(self.session.poll())

    def test_stale_or_mismatched_receipts_destroy_session(self):
        for key, value in [('sequence', 2), ('pid', 124), ('input_sha256', 'bad'),
                           ('output_sha256', 'bad'), ('reset', False),
                           ('temporal_accumulation', True), ('native_settings', {'other': 1})]:
            with self.subTest(key=key):
                original = self.receipt[key]
                self.receipt[key] = value
                self.publish()
                with self.assertRaises(ValueError):
                    self.session.poll()
                self.session.close.assert_called()
                self.receipt[key] = original

    def test_timeout_destroys_session(self):
        self.session.pending['started'] -= 61
        with self.assertRaises(TimeoutError):
            self.session.poll()
        self.session.close.assert_called_once()

    def test_unpublished_result_is_not_returned(self):
        self.assertIsNone(self.session.poll())
        self.session.close.assert_not_called()
