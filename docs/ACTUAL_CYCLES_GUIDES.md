> Архив предыдущих экспериментов. Не инструкция для 0.2.0. Актуальные [установка](QUICK_START.md), [совместимость](COMPATIBILITY.md), [управление](SETTINGS.md).

# Actual Cycles render guide export

`scripts/export_cycles_guides.py` exports Combined, Depth and Vector from Cycles
in an isolated scene copy. It writes 32-bit multilayer OpenEXR plus camera and
projection metadata. It does not run DLSS or change the installed viewport build.

Blender 5.2 requires `image_settings.media_type='MULTI_LAYER_IMAGE'` before setting
`OPEN_EXR_MULTILAYER`. Output uses multipart EXR: the reader must inspect all parts,
not just Combined. The validation uses upstream OpenEXR's multipart Python API.

## Verification

Cloud rendering run 34227482343 produced three valid exports and passed the
source-state checks. Its first validation failed because the legacy EXR reader
only inspected part zero; `check_cycles_guides.py` now reads every part. Rechecking
those original artifacts confirmed:

- Plane at camera Z=5: Depth is exactly 5 at the center and image edges.
- Perspective: identical depth with 1 and 8 samples, proving it must not be divided
  by sample count. The Z pass is axial distance, not distance along an oblique ray.
- Orthographic: Depth is also exactly 5.
- Projection conversion: perspective device depth 0.98009795; orthographic
  0.00490054, both match analytic near/far projection. Reversed depth sums with
  normal depth to one.
- Actual four-component Vector channels exist. This static fixture does not
  validate animated or deforming-object motion.

## Scope

This is a tested input stage for final-render processing. It is not yet connected
to Feeder/RenoDX, not an interactive viewport transport and not a DLSS-quality
validation. Raw Vector still needs its direction, units and frame timing converted
to the runtime contract. Projection convention must be explicitly configured.
The device-depth converter supports PERSP/ORTHO; panoramic/oblique projections
need separate treatment. Invalid or out-of-frustum depths map to the far plane
and are returned with an invalid mask.

The export disables compositor, sequencer, render border, multiview and motion
blur in the copy; metadata records this. It re-renders rather than reading an
existing F12 result. Original scene objects/materials are shared read-only.
