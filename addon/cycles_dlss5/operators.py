"""Non-destructive diagnostics."""

from __future__ import annotations

import subprocess
from pathlib import Path

import bpy

from .runtime_validation import (
    TARGET_GPU,
    classify_rtx,
    is_primary_target,
    validate_runtime,
)
from .backend import configure, has_backend


def _detect_nvidia_gpu() -> str:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "Unknown"
    return next((line.strip() for line in result.stdout.splitlines() if line.strip()), "Unknown")


class CYCLES_DLSS5_OT_diagnose(bpy.types.Operator):
    bl_idname = "cycles_dlss5.diagnose"
    bl_label = "Run Diagnostics"
    bl_description = "Check the current Blender, render engine, and NGX runtime"
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context):
        if bpy.app.version < (5, 2, 0):
            self.report({"ERROR"}, "Blender 5.2 or newer is required")
            return {"CANCELLED"}

        if not context.scene.render.engine.startswith("CYCLES"):
            self.report({"ERROR"}, "Select Cycles as the render engine")
            return {"CANCELLED"}

        addon = context.preferences.addons.get(__package__)
        if addon is None:
            self.report({"ERROR"}, "Cycles DLSS 5 preferences are unavailable")
            return {"CANCELLED"}

        preferences = addon.preferences
        gpu_name = _detect_nvidia_gpu()
        gpu_architecture = classify_rtx(gpu_name)
        preferences.detected_gpu = gpu_name
        if gpu_architecture == "UNKNOWN":
            preferences.diagnostic_summary = "No recognizable NVIDIA GeForce RTX GPU detected"
            self.report({"ERROR"}, preferences.diagnostic_summary)
            return {"CANCELLED"}

        try:
            report = validate_runtime(bpy.path.abspath(preferences.runtime_directory))
        except (FileNotFoundError, OSError, ValueError) as error:
            preferences.diagnostic_summary = str(error)
            self.report({"ERROR"}, preferences.diagnostic_summary)
            return {"CANCELLED"}

        preferences.runtime_sha256 = report.sha256
        if not report.recognized and not preferences.allow_unrecognized_runtime:
            preferences.diagnostic_summary = "Runtime fingerprint is not recognized; loading blocked"
            self.report({"ERROR"}, preferences.diagnostic_summary)
            return {"CANCELLED"}

        trust = report.label if report.recognized else "user-approved unrecognized runtime"
        support = (
            "primary test target"
            if is_primary_target(gpu_name)
            else f"experimental; planned validation target: {TARGET_GPU}"
        )
        preferences.diagnostic_summary = (
            f"File inspected: {gpu_architecture}, {trust}, {support}; NOT execution-tested"
        )
        self.report({"INFO"}, preferences.diagnostic_summary)
        return {"FINISHED"}


class CYCLES_DLSS5_OT_connect(bpy.types.Operator):
    bl_idname = "cycles_dlss5.connect"
    bl_label = "Enable DLSS"
    bl_description = "Configure files and select DLSS for viewport and final render; execution remains unverified"

    def execute(self, context):
        if not has_backend():
            self.report({"ERROR"}, "This Blender has no DLSS 5 Cycles backend. A patched build is required")
            return {"CANCELLED"}
        if bpy.app.is_job_running("RENDER"):
            self.report({"ERROR"}, "Finish the render before changing runtime paths")
            return {"CANCELLED"}
        addon = context.preferences.addons.get(__package__)
        if addon is None:
            return {"CANCELLED"}
        prefs = addon.preferences
        if context.scene.render.engine != 'CYCLES':
            self.report({'ERROR'}, 'Select Cycles first')
            return {'CANCELLED'}
        portable = Path(bpy.app.binary_path).parent
        if not prefs.runtime_directory:
            prefs.runtime_directory = str(portable / 'runtime')
        if not prefs.bridge_path:
            prefs.bridge_path = str(portable / 'dlss5nr_bridge.dll')
        gpu_name = _detect_nvidia_gpu()
        prefs.detected_gpu = gpu_name
        if classify_rtx(gpu_name) == "UNKNOWN":
            prefs.diagnostic_summary = "No recognizable NVIDIA GeForce RTX GPU detected"
            self.report({"ERROR"}, prefs.diagnostic_summary)
            return {"CANCELLED"}
        try:
            report = configure(
                bpy.path.abspath(prefs.runtime_directory) if prefs.runtime_directory else "",
                bpy.path.abspath(prefs.bridge_path) if prefs.bridge_path else "",
                prefs.allow_unrecognized_runtime,
                bpy.path.abspath(prefs.probe_report) if prefs.probe_report else '',
                prefs.output_order,
                prefs.allow_experimental_color,
            )
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            prefs.diagnostic_summary = str(error)
            prefs.show_advanced = True
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        prefs.runtime_sha256 = report.sha256
        settings = context.scene.cycles
        names = ('denoiser', 'preview_denoiser', 'use_denoising', 'use_preview_denoising')
        previous = {name: getattr(settings, name) for name in names}
        try:
            settings.denoiser = 'DLSS5NR'
            settings.preview_denoiser = 'DLSS5NR'
            settings.use_denoising = True
            settings.use_preview_denoising = True
        except (TypeError, ValueError, RuntimeError) as error:
            for name, value in previous.items():
                setattr(settings, name, value)
            prefs.diagnostic_summary = 'DLSS unavailable: enable an OptiX device in Cycles preferences'
            self.report({'ERROR'}, prefs.diagnostic_summary)
            return {'CANCELLED'}
        prefs.diagnostic_summary = "Probe passed; Blender rendering still unverified (independent frames)"
        self.report({"INFO"}, "DLSS selected for viewport and final render. Use Rendered shading to preview")
        return {"FINISHED"}

