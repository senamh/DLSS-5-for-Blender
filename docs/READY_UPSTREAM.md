> Архив предыдущих экспериментов. Не инструкция для 0.2.0. Актуальные [установка](QUICK_START.md), [совместимость](COMPATIBILITY.md), [управление](SETTINGS.md).

# DLSS5 viewport preview on RTX 5070

## Current route

Stock Blender 5.2.1, ReShade 6.8, upstream RenoDX and NVIDIA NR runtime, with a
small OpenGL compatibility patch to upstream DLSS5-Feeder 0.14.0-beta.5.
No custom tone mapper, sharpening filter, or neural model is substituted.

The guard resolves stale parent-resource mappings only when the actual OpenGL
view has the exact required size, format and sample count. It leaves upstream
validation and NGX processing intact. Build: run 34215265418. User-scene GPU
validation: run 34215539455 (feature 18 success; no input mismatch; normal exit).
Source pin: d69d9174ef055f95a657750db814c93ac1ad6c1d; patch:
`scripts/patch_feeder_gl_views.py`. MIT license and modified source accompany the
installed candidate. NVIDIA binaries are not distributed in this repository.

## Confirmed installation

[Run 34216277728](https://github.com/senamh/DLSS-5-for-Blender/actions/runs/34216277728)
completed with exit 0, NR confirmed, no input mismatch, F8 preserving view
rotation/distance, and programmatic orbit exercised. It installed
`C:\Users\User\Desktop\Blender-DLSS5-5070.cmd`, pointing to
`%LOCALAPPDATA%\DLSS-Blender\preview-5070-34216277728`.
The artifact `preview-controls-evidence` contains ReShade captures: present-1 ON,
present-2 OFF, present-3 ON again, present-4 after rotation. Visual inspection
confirms repeatable switching. The ON result is darker and smoother in this
scene; this is not evidence of improved fidelity or a demo-like transformation.

## Controls

The installation workflow verifies an isolated copy before creating the Desktop
launcher **Blender-DLSS5-5070.cmd**. Use it instead of the old Ready-TEST launcher.

1. Open the new launcher. Initial effect loading is delayed six seconds.
2. Open your scene with saved UI loading disabled; choose Cycles / Rendered.
3. Press F7 after opening a scene or resizing if effects need to reload.
4. Use F10 to toggle the Feeder technique for a same-view comparison.
5. F8 opens/closes advanced ReShade settings. Close this menu before navigating
   with the middle mouse button. Home retains Blender's normal frame-all action.
6. The N sidebar's DLSS 5 panel contains these controls. F6 captures the displayed
   result to the installation's Screenshots folder.

The startup script keeps the window presenting so the ReShade menu remains
responsive without restarting Cycles accumulation. Test scene files are read
without running their scripts and never saved by the verification workflow.

## Limits

- This processes the displayed application frame, including Blender UI; it is
  not a viewport-only native Cycles integration.
- F12 image files and animation exports do not include this effect.
- NGX evaluation success establishes execution, not accurate Cycles depth/motion
  guides, fidelity improvement, or the appearance of a particular demo video.
- Interactive navigation is exercised programmatically; no frame-rate target or
  long-session stability guarantee has been established.
- Older portrait evidence is insufficient for arbitrary Blender scene support.
  In run 34207206128 the third attempted ON screenshot remained OFF; do not use it
  as an ON comparison. The current route uses a technique hotkey instead.

Upstream: https://github.com/jlrouzies-fr/DLSS5-Feeder
