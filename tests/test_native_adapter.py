import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest

package = types.ModuleType('adapter_unit')
package.__path__ = [str(Path(__file__).resolve().parents[1]/'addon/cycles_dlss5')]
sys.modules[package.__name__] = package
adapter = importlib.import_module(package.__name__+'.native_frame_job')
payload = importlib.import_module(package.__name__+'.render_payload')


class AdapterTests(unittest.TestCase):
    def test_prepare_copies_input_and_invalidates_old_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, work = root/'input', root/'work'
            source.mkdir()
            work.mkdir()
            payload.prepare_image(source, bytes([50, 60, 70, 128])*96*96, 96, 96)
            job = adapter.NativeFrameJob.__new__(adapter.NativeFrameJob)
            job.folder, job.work, job.running = folder, work, False
            job.result = 'old'
            (work/'ngx_output.rgba8').write_bytes(b'old')
            job.prepare(source)
            self.assertIsNone(job.result)
            self.assertFalse((work/'ngx_output.rgba8').exists())
            self.assertEqual((work/'color.rgba8').read_bytes(), (source/'color.rgba8').read_bytes())
            job.running = True
            with self.assertRaises(ValueError):
                job.prepare(source)

    def test_unverified_finish_is_rejected(self):
        job = adapter.NativeFrameJob.__new__(adapter.NativeFrameJob)
        job.result = None
        with self.assertRaises(ValueError):
            job.finish(0)
