"""Isolated, cancellable upstream host job for an exported static Cycles frame."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from .frame_result import validate_payload, verify
from .style_config import native_values

# Same runtime set as the repository's isolated RTX evidence workflow.
RUNTIMES = {
    'opengl32.dll': ('dxgi.dll', '0cee63f9c9f13f3ac909c5b4903f4dbb4b719a7ab3b4f13b0deaf83c814b94f7'),
    'renodx-dlss5.addon64': ('renodx-dlss5.addon64', 'a8b5e164cbc3222a5d62bbddf44a2cc68d359b0caf729e55f2877c49e73e9aac'),
    'nvngx_dlss.dll': ('nvngx_dlss.dll', 'c85f971ce023c9f3492fc7455f0b01a24ba18ea39636407a846902c4360b0b7e'),
    'nvngx_dlssnr.dll': ('nvngx_dlssnr.dll', '4b8d19bc3eff58a084f5eca7489c921501c203450169fb82ff4f649a4482ba05'),
}


class FrameJob:
    def __init__(self, payload, host, runtime, settings=None):
        self.process = None
        self.log = None
        self.input_folder = None
        # Windows can briefly retain a directory handle after the GPU host exits.
        # Cleanup must not turn a verified render into a failed job.
        self.folder = tempfile.TemporaryDirectory(prefix='cycles-dlss5-frame-', ignore_cleanup_errors=True)
        self.root = Path(self.folder.name)
        try:
            payload, host, runtime = Path(payload), Path(host), Path(runtime)
            if not host.is_file() or host.suffix.lower() != '.exe':
                raise ValueError('Select the compiled upstream frame host executable')
            for name, (target, digest) in RUNTIMES.items():
                destination = self.root / target
                shutil.copyfile(runtime / name, destination)
                if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                    raise ValueError('Runtime differs from the tested set: ' + name)
            self.host = self.root / 'dlss5-feed-host64.exe'
            shutil.copyfile(host, self.host)
            # Private, verified copies live only for this session. Never cache
            # logs or outputs, and refuse reuse if a binary has changed.
            self.binaries = {p: self.signature(p) for p in
                             [self.host, *(self.root / target for target, _ in RUNTIMES.values())]}
            self.prepare(payload, settings)
        except Exception:
            self.close()
            raise

    @staticmethod
    def signature(path):
        stat = path.stat()
        return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns

    def prepare(self, payload, settings=None):
        """Reuse verified binaries, with fresh inputs and evidence for each run."""
        if self.folder is None:
            raise ValueError('Frame job is closed')
        if self.process is not None and self.process.poll() is None:
            raise ValueError('Cannot replace a running frame')
        for path, signature in self.binaries.items():
            if self.signature(path) != signature:
                raise ValueError('Cached runtime changed: ' + path.name)
        validate_payload(payload)
        if self.log is not None:
            self.log.close()
            self.log = None
        self.process = None
        if self.input_folder is not None:
            self.input_folder.cleanup()
        self.input_folder = tempfile.TemporaryDirectory(prefix='frame-', dir=self.root,
                                                        ignore_cleanup_errors=True)
        self.work = Path(self.input_folder.name)
        # These are only our own temporary logs, not the installed runtime's.
        for name in ('ReShade.log', 'console.log'):
            (self.root / name).unlink(missing_ok=True)
        for name in ('payload.json', 'color.rgba8', 'depth.f32', 'motion.f16'):
            shutil.copyfile(Path(payload) / name, self.work / name)
        self.meta = validate_payload(self.work)
        self.settings = native_values(settings) if settings is not None else {}
        self.progress_value = 15
        (self.root / 'ReShade.ini').write_text(
            '[ADDON]\nAddonPath=.\\\n[RenoDX.DLSS5]\nEnableHooks=2\nNeuralUplift=1\nNREnableUpscaling=0\nNRPreset=0\n'
            + ''.join(f'{key}={value}\n' for key, value in self.settings.items()))

    def start(self):
        self.log = (self.root / 'console.log').open('w')
        w, h = self.meta['size']
        env = os.environ.copy()
        # Never inherit the parent preview's profile or disable-log switches.
        for key in list(env):
            if key.startswith('RESHADE_'):
                del env[key]
        env['RESHADE_BASE_PATH_OVERRIDE'] = str(self.root)
        self.process = subprocess.Popen(
            [str(self.host), '--frame', str(w), str(h), str(self.work)],
            cwd=self.root, env=env, stdout=self.log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.started = time.monotonic()
        self.progress_value = 25

    def progress(self):
        """Completed workflow milestones, not a fabricated NVIDIA inference %.

        The runtime has no public per-frame percentage callback. Never animate
        time-based progress or report 100 before validation and publication.
        """
        for filename in ('console.log', 'ReShade.log'):
            try:
                with (self.root / filename).open('rb') as stream:
                    stream.seek(0, 2)
                    stream.seek(max(0, stream.tell() - 16384))
                    tail = stream.read().decode('utf-8', errors='replace')
                if '[frame] validated' in tail:
                    self.progress_value = max(self.progress_value, 45)
                if 'inline feature 18 evaluation succeeded' in tail:
                    self.progress_value = max(self.progress_value, 80)
            except OSError:
                pass
        try:
            if (self.work / 'ngx_output.rgba8').stat().st_size == self.meta['size'][0] * self.meta['size'][1] * 4:
                self.progress_value = max(self.progress_value, 90)
        except OSError:
            pass
        return self.progress_value

    def poll(self):
        code = self.process.poll()
        if code is None and time.monotonic() - self.started > 60:
            raise TimeoutError('Frame host exceeded 60 seconds')
        return code

    def finish(self, code, diagnostics=True):
        self.log.flush()
        report = verify(self.work, self.root / 'ReShade.log', code, diagnostics=diagnostics)
        report['native_settings'] = self.settings
        self.progress_value = 95
        return report

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.kill()
            self.process.wait(timeout=5)
        if self.log is not None:
            self.log.close()
            self.log = None
        if self.folder is not None:
            if self.input_folder is not None:
                self.input_folder.cleanup()
                self.input_folder = None
            self.folder.cleanup()
            self.folder = None
