"""Cycles DLSS 5 Blender extension entry point."""

from __future__ import annotations

import bpy
import sys

# The portable launcher also supports loading this package as a bundled add-on.
# Extension installs obtain metadata from blender_manifest.toml instead.
bl_info = {
    'name': 'Cycles DLSS 5',
    'author': 'Strela Industries',
    'version': (0, 2, 2),
    'blender': (5, 2, 0),
    'category': 'Render',
}

from .preferences import CYCLES_DLSS5_AddonPreferences
from .styles import CYCLES_DLSS5_Style, CYCLES_DLSS5_OT_style_preset
from .operators import CYCLES_DLSS5_OT_diagnose, CYCLES_DLSS5_OT_connect
from .backend import restore_environment
from .frame_operator import CYCLES_DLSS5_OT_frame, stop_frame
from .final_render import CLASSES as FINAL_CLASSES, register_handlers, unregister_handlers
from .viewport import CYCLES_DLSS5_OT_viewport, CYCLES_DLSS5_OT_viewport_stop
from .output import CYCLES_DLSS5_OT_output_folder
from .preview_launch import CYCLES_DLSS5_PT_preview_launcher
from . import shortcuts
from .setup_operator import CYCLES_DLSS5_OT_setup_check
from .panel import CYCLES_DLSS5_PT_render
from .probe_operator import CYCLES_DLSS5_OT_probe, stop_probe
from .stock import (CYCLES_DLSS5_OT_stock, CYCLES_DLSS5_OT_stock_stop,
                    CYCLES_DLSS5_PT_stock_view, stop_stock)


CLASSES = (
    CYCLES_DLSS5_Style,
    CYCLES_DLSS5_OT_style_preset,
    CYCLES_DLSS5_AddonPreferences,
    CYCLES_DLSS5_PT_preview_launcher,
    CYCLES_DLSS5_OT_frame,
    CYCLES_DLSS5_OT_probe,
    CYCLES_DLSS5_OT_diagnose,
    CYCLES_DLSS5_OT_connect,
    CYCLES_DLSS5_OT_stock,
    CYCLES_DLSS5_OT_stock_stop,
    *FINAL_CLASSES,
    CYCLES_DLSS5_OT_viewport,
    CYCLES_DLSS5_OT_viewport_stop,
    CYCLES_DLSS5_OT_output_folder,
    *shortcuts.CLASSES,
    CYCLES_DLSS5_OT_setup_check,
)


def register() -> None:
    # A bundled launcher and a bl_ext installation must not own two interfaces.
    current = sys.modules[__name__]
    for name, module in list(sys.modules.items()):
        if module is current or not (name == 'cycles_dlss5' or name.endswith('.cycles_dlss5')):
            continue
        classes = getattr(module, 'CLASSES', ())
        if any(getattr(cls, 'is_registered', False) for cls in classes):
            module.unregister()
    if getattr(bpy, '_cycles_dlss5_owner', None) is current:
        return
    registered = []
    try:
        for cls in CLASSES:
            bpy.utils.register_class(cls)
            registered.append(cls)
        bpy.types.Scene.dlss5_style = bpy.props.PointerProperty(type=CYCLES_DLSS5_Style)
        register_handlers()
        shortcuts.register()
        bpy._cycles_dlss5_owner = current
    except Exception:
        shortcuts.unregister()
        unregister_handlers()
        if hasattr(bpy.types.Scene, 'dlss5_style'):
            del bpy.types.Scene.dlss5_style
        for cls in reversed(registered):
            bpy.utils.unregister_class(cls)
        raise


def unregister() -> None:
    if getattr(bpy, '_cycles_dlss5_owner', None) is not sys.modules[__name__]:
        return
    unregister_handlers()
    shortcuts.unregister()
    stop_frame()
    stop_stock()
    stop_probe()
    restore_environment()
    del bpy.types.Scene.dlss5_style
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    del bpy._cycles_dlss5_owner
