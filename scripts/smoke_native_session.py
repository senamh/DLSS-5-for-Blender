"""Exercise experimental session lifecycle on an explicitly supplied native runtime."""
import argparse
import json
from pathlib import Path
import sys
import time
import types

import numpy as np
from PIL import Image

package = types.ModuleType('session_addon')
package.__path__ = [str(Path(__file__).resolve().parents[1]/'addon/cycles_dlss5')]
sys.modules['session_addon'] = package
from session_addon.native_session import NativeSession


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('image', 'bridge', 'runtime', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--blender', type=Path, help='Run worker in Blender bundled Python')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    frame = np.asarray(Image.open(args.image).convert('RGBA'), dtype=np.float32)/255
    frame[:, :, :3] = np.where(frame[:, :, :3] <= .04045, frame[:, :, :3]/12.92,
                               ((frame[:, :, :3]+.055)/1.055)**2.4)
    settings = dict(style='0', intensity=1, tone=1, structure=1, skin=-1, auto_mask=False)
    command = ([str(args.blender), '--background', '--factory-startup', '--disable-autoexec',
                '--python-exit-code', '1', '--python'] if args.blender else [sys.executable])
    report = {'worker_command': command, 'size': [int(frame.shape[1]), int(frame.shape[0])]}

    def new():
        return NativeSession(command, args.bridge, args.runtime)

    def receive(session):
        while True:
            result = session.poll()
            if result is not None:
                return result
            time.sleep(.01)

    session = new()
    try:
        session.submit(frame, settings)
        first, receipt = receive(session)
        report['first'] = receipt
        np.save(args.output/'output.npy', first, allow_pickle=False)
        session.submit(frame, settings)
        try:
            session.submit(frame, settings)
            raise AssertionError('Overlapping submission accepted')
        except RuntimeError:
            report['overlap_rejected'] = True
        second, receipt = receive(session)
        report['repeat'] = receipt
        assert np.array_equal(first, second)
        assert receipt['pid'] == report['first']['pid']
        session.submit(frame, settings)
        session.close()
        assert session.process.poll() is not None and session.poll() is None
        report['cancelled'] = True
    finally:
        session.close()
    session = new()
    try:
        session.submit(frame, settings)
        session.process.kill()
        session.process.wait(timeout=5)
        try:
            session.poll()
            raise AssertionError('Dead worker accepted')
        except RuntimeError:
            report['crash_detected'] = True
        assert session.folder is None
    finally:
        session.close()
    session = new()
    try:
        session.submit(frame, settings)
        recovered, receipt = receive(session)
        assert np.array_equal(first, recovered)
        report['recovered'] = receipt
        report['recovery_identical'] = True
    finally:
        session.close()
    (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
