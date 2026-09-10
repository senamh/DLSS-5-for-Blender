> Архив предыдущих экспериментов. Не инструкция для 0.2.0. Актуальные [установка](QUICK_START.md), [совместимость](COMPATIBILITY.md), [управление](SETTINGS.md).

# Cycles guide audit — 2026-09-08

## Established from source

Blender 5.2.1 source pin: `9e2066aef7ef7e20c142ad7bd3303138a4304c93`.

- `intern/cycles/blender/display_driver.cpp`: the display driver uploads and draws
  RGBA image tiles. This path does not export the Cycles Z pass to ReShade.
- `source/blender/draw/engines/external/external_engine.cc`: rendered view drawing
  sets `DRW_STATE_WRITE_COLOR`. A separate surface-depth prepass is enabled for
  Grease Pencil integration; the source explicitly says it should ultimately be
  replaced by render-engine depth output.
- Upstream Feeder `shaders/DLSS5_Feed.fx` at
  `d69d9174ef055f95a657750db814c93ac1ad6c1d`: `RawDepth()` samples
  `ReShade::DepthBuffer` into a full-window texture. It does not read Cycles Z.

These facts establish a missing direct Cycles-depth connection, not proof that
all selected hardware depth buffers are empty or that this alone explains image
quality. Overlay geometry may provide approximate depth. The previous OpenGL
view fix validates resource identity/shape, not geometric alignment or semantics.

## GPU experiment

Workflow: `audit-depth.yml`; scripts: `audit_depth.py`, `audit_depth_ui.py`.

Uses a separate copy of the verified preview, opens the saved project without
scripts or saved UI, and never saves the project. Enables upstream
`DLSS5_Feed_Debug` with `DEBUG_VIEW=1` (raw-depth diagnostic), disables Feeder
neural evaluation so it cannot transform the diagnostic, then requests ReShade
screenshots with Blender overlays on and off. Records viewport/window bounds.
It does not change the working Desktop launcher or installation.

Inspect both actual screenshots and shader logs; a green workflow alone does
not validate the guides. No GPU conclusion is recorded until this completes.

## Acceptance before native render integration

- Visible surface depth must align with the corresponding color pixels, including
  viewport offsets, camera framing, orientation, background and resizing.
- Distinguish raw device depth from Cycles camera-space/ray-distance Z. Conversion
  must follow the selected projection and runtime contract, not normalization by
  observed min/max.
- Motion must refer to consecutive evaluated images and handle scene changes;
  camera-only reprojection is insufficient for moving/deforming objects.
- F12 integration must consume and produce render buffers independently of the
  desktop/UI. ReShade screenshots cannot serve as final-render integration.

Existing native patches are prototypes, not an automatically accepted fallback.
They require their own input-contract and color-management review before reuse.

## Cloud execution (software OpenGL)

The cloud experiment runs official checksum-pinned Blender 5.2.1 on Ubuntu 22.04,
Mesa llvmpipe, Xvfb and Cycles CPU. It uses the factory cube scene, not the user's
private project. No NVIDIA runtime or ReShade binary is loaded in this test.

Repeated measurements of the framebuffer bound at POST_VIEW and POST_PIXEL:

| Mode | Depth minimum | Depth maximum | Distinct values |
| --- | ---: | ---: | ---: |
| Cycles, overlays on | 0.5005000 | 1.0 | 60,546 |
| Cycles, overlays off | 1.0 | 1.0 | 1 |
| Solid, overlays off (control) | 0.9847332 | 1.0 | 23,497 |

Each buffer has 785 x 545 = 427,825 pixels. In the Cycles overlays-off case, all
pixels equal the cleared depth value. Solid produces geometry depth without
overlays, so this is not a universally empty software-OpenGL readback.

Important scope: Blender's draw-handler framebuffer can contain only the overlay
layer. Its color readback must not be described as the final Cycles image. We
therefore capture the X display separately with ImageMagick's window capture.
Blender's screenshot operator returned black in this virtual-display setup; the
first external capture was obscured by first-launch setup. Isolated preferences
are now initialized before launching the UI to remove that obstruction.

This confirms overlay-dependent availability of depth at the tested Blender
callbacks. It does not identify which resource ReShade selects on Windows, prove
that missing depth is the sole cause of weak neural results, or measure DLSS
quality/performance. The pending Windows diagnostic remains relevant for those
questions. Do not advertise this as a cloud DLSS/RTX validation.

Final cloud run:
[34221152476](https://github.com/senamh/DLSS-5-for-Blender/actions/runs/34221152476).
The unobscured X-display screenshot visibly shows the Cycles-rendered cube while
all 427,825 captured depth values remain 1.0 with overlays off. The control and
all six readbacks completed without readback errors. The artifact contains raw
NumPy depth arrays, JSON measurements, framebuffer captures and X screenshots.
