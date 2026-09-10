"""One owned native worker; serialized frames, verified receipts, bounded lifetime.

Experimental DISPLAY_LINEAR backend. Does not enable temporal accumulation or
automatically replace the RenoDX backend. Blender API calls stay in the parent.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

import numpy as np
from .style_config import native_values


class NativeSession:
    def __init__(self, command_prefix, bridge, runtime, timeout=60):
        self.folder = tempfile.TemporaryDirectory(prefix='dlss5-native-session-', ignore_cleanup_errors=True)
        self.root = Path(self.folder.name)
        self.process = None
        self.log = None
        self.pending = None
        self.sequence = 0
        self.timeout = timeout
        self.configuration = dict(bridge=str(Path(bridge).resolve()),
            runtime=str(Path(runtime).resolve()), order='RGB', color_mode='DISPLAY_LINEAR',
            input=str(self.root/'input.npy'), output=str(self.root/'output.npy'))
        try:
            self.log = (self.root/'worker.log').open('w', encoding='utf-8')
            self.process = subprocess.Popen([*command_prefix,
                str(Path(__file__).with_name('stock_worker.py')), '--', str(self.root/'job.json'), '--serve'],
                stdout=self.log, stderr=subprocess.STDOUT,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception:
            self.close()
            raise

    def submit(self, frame, settings):
        if self.folder is None or self.process.poll() is not None:
            raise RuntimeError('Native session is closed; create a new session')
        if self.pending is not None:
            raise RuntimeError('A native frame is already in flight')
        expected_settings = native_values(settings)
        frame = np.array(frame, dtype=np.float32, copy=True, order='C')
        if (frame.ndim != 3 or frame.shape[2] != 4 or
                not all(96 <= n <= 4096 for n in frame.shape[:2]) or
                not np.isfinite(frame).all() or np.any(frame < 0) or np.any(frame > 1)):
            raise ValueError('DISPLAY_LINEAR requires finite RGBA [0,1], dimensions 96..4096')
        np.save(self.root/'input.npy', frame, allow_pickle=False)
        job = dict(self.configuration, settings=dict(settings))
        temporary = self.root/'job.tmp'
        temporary.write_text(json.dumps(job), encoding='utf-8')
        temporary.replace(self.root/'job.json')
        self.sequence += 1
        self.pending = dict(sequence=self.sequence, frame=frame, settings=expected_settings,
                            started=time.monotonic())
        request = self.root/'request.tmp'
        request.write_text(json.dumps({'sequence': self.sequence}), encoding='utf-8')
        request.replace(self.root/f'request-{self.sequence}.json')

    def poll(self):
        if self.pending is None:
            return None
        try:
            if self.process.poll() is not None:
                self.log.flush()
                detail = (self.root/'worker.log').read_text(encoding='utf-8', errors='replace')[-2000:]
                raise RuntimeError('Native worker exited: ' + detail)
            if time.monotonic()-self.pending['started'] > self.timeout:
                raise TimeoutError('Native frame timed out')
            path = self.root/f'done-{self.sequence}.json'
            if not path.exists():
                return None
            try:
                receipt = json.loads(path.read_text(encoding='utf-8'))
                result = np.load(self.root/'output.npy', allow_pickle=False)
            except PermissionError:
                return None
            source = self.pending['frame']
            if (receipt.get('sequence') != self.sequence or receipt.get('pid') != self.process.pid or
                    receipt.get('native_settings') != self.pending['settings'] or
                    receipt.get('reset') is not True or receipt.get('temporal_accumulation') is not False or
                    receipt.get('input_sha256') != hashlib.sha256(source.tobytes()).hexdigest() or
                    result.shape != source.shape or result.dtype != np.float32 or
                    not np.isfinite(result).all() or not np.array_equal(result[:,:,3], source[:,:,3]) or
                    receipt.get('output_sha256') != hashlib.sha256(result.tobytes()).hexdigest()):
                raise ValueError('Native receipt/output does not match the submitted frame')
            receipt['round_trip_seconds'] = time.monotonic()-self.pending['started']
            for consumed in (path, self.root/f'request-{self.sequence}.json'):
                try:
                    consumed.unlink()
                except PermissionError:
                    pass
            self.pending = None
            return result, receipt
        except Exception:
            self.close()
            raise

    def close(self):
        """Cancellation destroys the worker, so a late result cannot be published."""
        self.pending = None
        if self.process is not None and self.process.poll() is None:
            (self.root/'stop').touch()
            try:
                self.process.wait(timeout=.25)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        if self.log is not None:
            self.log.close()
            self.log = None
        if self.folder is not None:
            self.folder.cleanup()
            self.folder = None
