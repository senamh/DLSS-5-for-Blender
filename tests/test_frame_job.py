"""Run the evidence gate and isolated host lifecycle without GPU hardware."""
import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType('_frame_tests')
package.__path__ = [str(ROOT / 'addon/cycles_dlss5')]
sys.modules['_frame_tests'] = package

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

job_module = load('_frame_tests.frame_job', ROOT / 'addon/cycles_dlss5/frame_job.py')
# Run the existing five evidence tests against the packaged implementation.
with patch.dict(sys.modules, {'verify_frame_result': sys.modules['_frame_tests.frame_result']}):
    gate = load('_frame_gate_tests', ROOT / 'scripts/test_frame_result_gate.py')

class FrameJobTests(gate.ResultGate):
    def make_job(self):
        host = self.root / 'host.exe'
        host.write_bytes(b'test fixture, never executed')
        with patch.object(job_module, 'RUNTIMES', {}):
            job = job_module.FrameJob(self.root, host, self.root)
        self.addCleanup(job.close)
        return job

    def test_old_output_and_log_not_copied(self):
        job = self.make_job()
        self.assertFalse((job.work / 'ngx_output.rgba8').exists())
        self.assertFalse((job.root / 'ReShade.log').exists())
        self.assertEqual((job.work / 'color.rgba8').read_bytes(), self.color)

    def test_cancel_reaps_process(self):
        job = self.make_job()
        process = Mock()
        process.poll.return_value = None
        with patch.object(job_module.subprocess, 'Popen', return_value=process):
            job.start()
        job.close()
        process.kill.assert_called_once()
        process.wait.assert_called_once_with(timeout=5)
        self.assertFalse(job.root.exists())

    def test_timeout(self):
        job = self.make_job()
        job.process = Mock()
        job.process.poll.return_value = None
        job.started = 0
        with patch.object(job_module.time, 'monotonic', return_value=61):
            with self.assertRaises(TimeoutError):
                job.poll()

    def test_runtime_mismatch(self):
        job = self.make_job()
        with patch.object(job_module, 'RUNTIMES', {'color.rgba8': ('dxgi.dll', 'bad')}):
            with self.assertRaisesRegex(ValueError, 'Runtime differs'):
                job_module.FrameJob(self.root, job.host, self.root)

    def test_reuse_has_fresh_evidence_and_no_binary_copy(self):
        job = self.make_job()
        old_work = job.work
        (job.root / 'ReShade.log').write_text('inline feature 18 evaluation succeeded')
        (job.work / 'ngx_output.rgba8').write_bytes(self.color)
        with patch.object(job_module.shutil, 'copyfile', wraps=job_module.shutil.copyfile) as copy:
            job.prepare(self.root)
        self.assertEqual(copy.call_count, 4)
        self.assertNotEqual(job.work, old_work)
        self.assertFalse(old_work.exists())
        self.assertFalse((job.root / 'ReShade.log').exists())
        self.assertFalse((job.work / 'ngx_output.rgba8').exists())

    def test_reuse_rejects_changed_binary(self):
        job = self.make_job()
        job.host.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Cached runtime changed'):
            job.prepare(self.root)

    def test_reuse_rejects_running_or_closed(self):
        job = self.make_job()
        job.process = Mock()
        job.process.poll.return_value = None
        with self.assertRaisesRegex(ValueError, 'running frame'):
            job.prepare(self.root)
        job.close()
        with self.assertRaisesRegex(ValueError, 'closed'):
            job.prepare(self.root)

    def test_progress_requires_real_milestones_and_never_claims_finished(self):
        job = self.make_job()
        self.assertEqual(job.progress(), 15)
        (job.root / 'console.log').write_text('[frame] validated 128x96')
        self.assertEqual(job.progress(), 45)
        (job.root / 'ReShade.log').write_text('inline feature 18 evaluation succeeded')
        self.assertEqual(job.progress(), 80)
        (job.work / 'ngx_output.rgba8').write_bytes(self.color)
        self.assertEqual(job.progress(), 90)
        self.assertLess(job.progress(), 100)
