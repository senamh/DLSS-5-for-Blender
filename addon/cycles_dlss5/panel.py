"""Cycles render properties UI."""

from __future__ import annotations

import bpy
from .backend import has_backend
from .preview_launch import draw_preview


class CYCLES_DLSS5_PT_render(bpy.types.Panel):
    bl_label = "DLSS 5 Neural Rendering"
    bl_idname = "CYCLES_DLSS5_PT_render"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.scene is not None and context.scene.render.engine.startswith("CYCLES")

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        available = has_backend()
        layout.label(text="Experimental native backend" if available else "DLSS Preview integration", icon="INFO")
        addon = context.preferences.addons.get(__package__)
        if addon is not None:
            preferences = addon.preferences
            layout.label(text=f"GPU: {preferences.detected_gpu}")
            layout.label(text=preferences.diagnostic_summary)
            draw_preview(layout, preferences, context)
            row = layout.row()
            row.enabled = available
            row.scale_y = 1.5
            row.operator("cycles_dlss5.connect", icon="PLUGIN")
            layout.prop(preferences, 'show_advanced', toggle=True)
            if preferences.show_advanced:
                box = layout.box()
                box.label(text='Legacy bridge and developer tests')
                box.operator('cycles_dlss5.probe', icon='CHECKMARK')
                box.operator('cycles_dlss5.stock', text='Legacy F12 Postprocess (experimental)')
                box.operator('cycles_dlss5.frame')
                box.label(text='Payload command requires exported guides')
                box.prop(preferences, "runtime_directory")
                box.prop(preferences, "bridge_path")
                box.prop(preferences, 'allow_unrecognized_runtime')
                box.prop(preferences, 'output_order')
                box.prop(preferences, 'probe_report')
                box.prop(preferences, 'allow_experimental_color')
                box.label(text='Approve only files you trust; compatibility is unverified.')
                box.operator('cycles_dlss5.diagnose', icon='CHECKMARK')
        if not available:
            return
        settings = context.scene.cycles
        layout.label(text='Appearance effect; FPS improvement is not guaranteed.')
        layout.label(text='Independent frames; temporal stabilization unavailable.')
        layout.prop(settings, "use_preview_denoising", text="Viewport Denoising")
        layout.prop(settings, "use_denoising", text="Final Denoising")
        if settings.denoiser == 'DLSS5NR' or settings.preview_denoiser == 'DLSS5NR':
            layout.prop(settings, 'dlss5nr_intensity', text='Effect Strength')
        if addon is None or not addon.preferences.show_advanced:
            return
        layout.prop(settings, 'preview_denoiser')
        layout.prop(settings, 'denoiser')
        if settings.denoiser == 'DLSS5NR' or settings.preview_denoiser == 'DLSS5NR':
            for name in ("style", "tone", "structure", "auto_mask"):
                layout.prop(settings, "dlss5nr_" + name)
            row = layout.row()
            row.enabled = settings.dlss5nr_auto_mask
            row.prop(settings, "dlss5nr_skin")
