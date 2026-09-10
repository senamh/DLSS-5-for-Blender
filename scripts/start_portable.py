"""Enable the bundled UI for this session; never load a neural runtime here."""
import sys
from pathlib import Path

import addon_utils
import bpy


def enable_ui():
    root = Path(bpy.app.binary_path).parent
    addon_path = str(root / 'dlss5-addon')
    if addon_path not in sys.path:
        sys.path.insert(0, addon_path)

    def fail(error):
        raise error

    module = addon_utils.enable('cycles_dlss5', default_set=True,
                                persistent=True, handle_error=fail)
    if module is None:
        raise RuntimeError('Bundled Cycles DLSS 5 panel could not be enabled')
    return module


if __name__ == '__main__':
    enable_ui()

