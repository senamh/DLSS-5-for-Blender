"""Non-blocking probe in a disposable Blender process, never the artist's process."""
import json
from pathlib import Path
import subprocess
import time
import uuid

import bpy
from .probe import identity, require_receipt
from .runtime_validation import validate_runtime

_active = None


def stop_probe():
    global _active
    if _active is not None:
        _active.cleanup()
        _active = None


class CYCLES_DLSS5_OT_probe(bpy.types.Operator):
    bl_idname = 'cycles_dlss5.probe'
    bl_label = 'Test Runtime'
    bl_description = 'Process a color chart in a separate process before enabling DLSS'
    _process = None
    _timer = None
    _log = None
    _manager = None

    def execute(self, context):
        global _active
        if _active is not None:
            self.report({'ERROR'}, 'A runtime test is already running')
            return {'CANCELLED'}
        prefs = context.preferences.addons[__package__].preferences
        portable = Path(bpy.app.binary_path).parent
        if not prefs.runtime_directory:
            prefs.runtime_directory = str(portable / 'runtime')
        if not prefs.bridge_path:
            prefs.bridge_path = str(portable / 'dlss5nr_bridge.dll')
        prefs.probe_report = ''
        try:
            runtime = bpy.path.abspath(prefs.runtime_directory)
            bridge = bpy.path.abspath(prefs.bridge_path)
            report = validate_runtime(runtime)
            if not report.recognized and not prefs.allow_unrecognized_runtime:
                raise ValueError('Approve your trusted runtime in Advanced before running the test')
            self._expected = identity(runtime, bridge, prefs.output_order)
            folder = bpy.utils.user_resource('CONFIG', path='cycles_dlss5/probes', create=True)
            if not folder:
                raise ValueError('Cannot create the runtime test folder')
            self._output = Path(folder) / uuid.uuid4().hex
            self._output.mkdir()
            self._log = (self._output / 'worker.log').open('w', encoding='utf-8')
            command = [bpy.app.binary_path, '--background', '--factory-startup',
                       '--python-exit-code', '1', '--python', str(Path(__file__).with_name('probe.py')),
                       '--', '--worker', '--trust-runtime', '--runtime', runtime,
                       '--bridge', bridge, '--order', prefs.output_order,
                       '--output', str(self._output)]
            self._process = subprocess.Popen(command, stdout=self._log, stderr=subprocess.STDOUT)
            self._started = time.monotonic()
            self._manager = context.window_manager
            self._timer = self._manager.event_timer_add(0.25, window=context.window)
            self._manager.modal_handler_add(self)
            _active = self
            prefs.diagnostic_summary = 'Testing three frames in a separate process; Esc cancels'
            return {'RUNNING_MODAL'}
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.cleanup()
            prefs.show_advanced = True
            prefs.diagnostic_summary = str(error)
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}

    def cleanup(self):
        if self._process is not None and self._process.poll() is None:
            self._process.kill()
            self._process.wait(timeout=5)
        if self._timer is not None:
            self._manager.event_timer_remove(self._timer)
            self._timer = None
        if self._log is not None:
            self._log.close()
            self._log = None

    def modal(self, context, event):
        global _active
        prefs = context.preferences.addons[__package__].preferences
        failure = None
        if event.type == 'ESC':
            failure = 'Runtime test cancelled'
        elif event.type != 'TIMER':
            return {'PASS_THROUGH'}
        elif time.monotonic() - self._started > 120:
            failure = 'Runtime test timed out; see worker.log'
        elif self._process.poll() is None:
            return {'RUNNING_MODAL'}
        elif self._process.returncode != 0:
            failure = f'Runtime process failed ({self._process.returncode}); see {self._output}'
        try:
            if failure:
                raise ValueError(failure)
            current = identity(bpy.path.abspath(prefs.runtime_directory),
                               bpy.path.abspath(prefs.bridge_path), prefs.output_order)
            if current != self._expected:
                raise ValueError('Configuration changed during test; repeat it')
            receipt = self._output / 'report.json'
            require_receipt(receipt, current)
            prefs.probe_report = str(receipt)
            prefs.diagnostic_summary = 'Three-frame test passed; inspect input.ppm and output.ppm before enabling'
            self.report({'INFO'}, f'Test images and timings: {self._output}')
            return {'FINISHED'}
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            prefs.probe_report = ''
            prefs.diagnostic_summary = str(error)
            prefs.show_advanced = True
            # A native fault after report writing must invalidate that report.
            (self._output / 'report.json').write_text(
                json.dumps({'passed': False, 'error': str(error)}), encoding='utf-8')
            self.report({'ERROR'}, str(error))
            return {'CANCELLED'}
        finally:
            self.cleanup()
            _active = None

