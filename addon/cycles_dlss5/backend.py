"""Session configuration; never loads a native library during diagnostics."""

import os
import sys
from pathlib import Path

from .runtime_validation import validate_runtime
from .probe import identity, require_receipt

_previous_environment = {}


def configure(runtime_directory, bridge_path, allow_unknown=False,
              probe_report='', output_order='RGB', allow_experimental_color=False):
    if sys.platform != "win32":
        raise ValueError("The native DLSS 5 backend requires Windows x64")
    if not runtime_directory.strip() or not bridge_path.strip():
        raise ValueError("Select both the runtime folder and the native bridge DLL")
    report = validate_runtime(runtime_directory)
    if not report.recognized and not allow_unknown:
        raise ValueError("Unknown runtime: inspect its source and explicitly allow it first")
    bridge = Path(bridge_path).resolve(strict=True)
    shim = report.path.parent / "caller" / "nvngx.dll_blender.dll"
    if not bridge.is_file() or bridge.name.lower() != "dlss5nr_bridge.dll":
        raise ValueError("Select the built dlss5nr_bridge.dll")
    if not shim.is_file():
        raise ValueError("Missing runtime/caller/nvngx.dll_blender.dll; build the caller shim")
    require_receipt(probe_report, identity(runtime_directory, bridge, output_order))
    if not allow_experimental_color:
        raise ValueError('Review the test images and explicitly allow experimental color processing')
    values = {
        "CYCLES_DLSS5NR_RUNTIME": str(report.path.parent.resolve()),
        "CYCLES_DLSS5NR_BRIDGE": str(bridge),
        'CYCLES_DLSS5NR_OUTPUT_ORDER': output_order,
    }
    for key, value in values.items():
        _previous_environment.setdefault(key, os.environ.get(key))
        os.environ[key] = value
    return report


def restore_environment():
    for key, value in _previous_environment.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    _previous_environment.clear()


def has_backend():
    try:
        import _cycles
        return bool(getattr(_cycles, "with_dlss5nr", False))
    except ImportError:
        return False

