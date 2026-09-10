"""Regress the reported transient Windows request-file sharing failure."""
import importlib.util
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch, Mock

source = Path(__file__).resolve().parents[1]/'addon/cycles_dlss5/stock_worker.py'
spec = importlib.util.spec_from_file_location('mailbox_worker', source)
worker = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'numpy': Mock()}):
    spec.loader.exec_module(worker)


class MailboxTests(unittest.TestCase):
    def test_wrong_sequence_cannot_acknowledge_another_frame(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'request-1.json').write_text(json.dumps({'sequence': 2}))
            with patch.object(worker, 'process') as process:
                with self.assertRaises(ValueError):
                    worker.serve(root/'job.json')
                process.assert_not_called()
            self.assertFalse((root/'done-2.json').exists())

    def test_invalid_settings_rejected_before_native_load(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'job.json'
            path.write_text(json.dumps({'settings': {'style': '2'}}))
            with patch.object(worker.ctypes, 'CDLL') as load:
                with self.assertRaises(ValueError):
                    worker.process(path)
                load.assert_not_called()

    def test_done_receipt_includes_native_frame_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'request-1.json').write_text(json.dumps({'sequence': 1}))
            def process(_):
                (root/'stop').touch()
                return {'pid': 123, 'reset': True, 'native_settings': {'NRStyle': '0'}}
            with patch.object(worker, 'process', process):
                worker.serve(root/'job.json')
            receipt = json.loads((root/'done-1.json').read_text())
            self.assertEqual(receipt['pid'], 123)
            self.assertEqual(receipt['native_settings'], {'NRStyle': '0'})

    def test_locked_request_is_retried_and_acknowledged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'request-1.json').write_text(json.dumps({'sequence': 1}))
            original_read = Path.read_text
            attempts = []

            def read(path, *args, **kwargs):
                if path.name == 'request-1.json':
                    attempts.append(1)
                    if len(attempts) == 1:
                        raise PermissionError(13, 'Windows sharing violation')
                return original_read(path, *args, **kwargs)

            def process(_):
                (root/'stop').touch()

            with patch.object(Path, 'read_text', read), patch.object(worker, 'process', process):
                worker.serve(root/'job.json')
            self.assertEqual(len(attempts), 2)
            self.assertEqual(json.loads((root/'done-1.json').read_text())['sequence'], 1)


if __name__ == '__main__':
    unittest.main()
