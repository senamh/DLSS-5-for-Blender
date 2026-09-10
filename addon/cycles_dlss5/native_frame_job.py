"""Experimental FrameJob-compatible SDR adapter; isolated pinned native binaries."""
import hashlib
from pathlib import Path
import shutil
import tempfile

import numpy as np
from .frame_result import validate_payload
from .native_session import NativeSession
from .style_config import PRESETS, FIELDS

PINNED = {
    'dlss5nr_bridge.dll': '7564e5ffed33bc29f354a53d6030dceb4c7809467583b5eb4c6ace274792298e',
    'nvngx_dlssnr.dll': '6eb209e764f39872625debd6abaf45e2bb6322f6f270f781f70c059ae30b3927',
    'caller/nvngx.dll_blender.dll': '40cfd0db20d80b300bfdac1075e9334d6d630826e25a26868122f2aeb88a5171',
}


class NativeFrameJob:
    def __init__(self, payload, command, bridge, runtime, settings=None):
        self.folder = tempfile.TemporaryDirectory(prefix='dlss5-native-job-', ignore_cleanup_errors=True)
        self.root = Path(self.folder.name)
        self.work = self.root/'frame'
        self.work.mkdir()
        self.session = None
        self.result = None
        self.running = False
        try:
            for name, digest in PINNED.items():
                source = Path(bridge) if name == 'dlss5nr_bridge.dll' else Path(runtime)/name
                target = self.root/'runtime'/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    raise ValueError('Experimental runtime differs from tested set: '+name)
            self.session = NativeSession(command, self.root/'runtime/dlss5nr_bridge.dll', self.root/'runtime')
            self.prepare(payload, settings)
        except Exception:
            self.close()
            raise

    def prepare(self, payload, settings=None):
        if self.folder is None or self.running:
            raise ValueError('Native job is closed or busy')
        self.meta = validate_payload(payload)
        # This adapter has no guide-input ABI; refuse silently dropping real depth.
        if (Path(payload)/'depth.f32').read_bytes() != b'\x00\x00\x80\x3f'*(self.meta['size'][0]*self.meta['size'][1]):
            raise ValueError('Experimental native adapter accepts image-only far depth')
        shutil.copyfile(Path(payload)/'color.rgba8', self.work/'color.rgba8')
        self.settings = dict(settings) if settings is not None else dict(zip(FIELDS, PRESETS['BALANCED']))
        self.result = None
        (self.work/'ngx_output.rgba8').unlink(missing_ok=True)

    def start(self):
        if self.running:
            raise ValueError('Native job is busy')
        w, h = self.meta['size']
        frame = np.frombuffer((self.work/'color.rgba8').read_bytes(), dtype=np.uint8).reshape(h, w, 4).astype(np.float32)/255
        rgb = frame[:, :, :3]
        frame[:, :, :3] = np.where(rgb <= .04045, rgb/12.92, ((rgb+.055)/1.055)**2.4)
        self.session.submit(frame, self.settings)
        self.running = True

    def poll(self):
        if self.result is not None:
            return 0
        if not self.running:
            raise ValueError('Native job has not started')
        self.result = self.session.poll()
        return 0 if self.result is not None else None

    def progress(self):
        return 90 if self.result is not None else 25

    def finish(self, code, diagnostics=True):
        if code != 0 or self.result is None:
            raise ValueError('Native frame is not verified')
        frame, receipt = self.result
        rgba = np.clip(frame, 0, 1).copy()
        rgb = rgba[:, :, :3]
        rgba[:, :, :3] = np.where(rgb <= .0031308, rgb*12.92, 1.055*rgb**(1/2.4)-.055)
        data = np.rint(rgba*255).astype(np.uint8).tobytes()
        (self.work/'ngx_output.rgba8').write_bytes(data)
        self.running = False
        return dict(receipt, backend='experimental-native-display-linear', size=self.meta['size'],
                    hdr_verified=False, quality_improvement_confirmed=False,
                    binary_sha256=PINNED.copy(), published_output_sha256=hashlib.sha256(data).hexdigest())

    def close(self):
        if self.session is not None:
            self.session.close()
            self.session = None
        if self.folder is not None:
            self.folder.cleanup()
            self.folder = None
