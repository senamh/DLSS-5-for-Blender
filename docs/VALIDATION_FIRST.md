> Архив предыдущих экспериментов. Не инструкция для 0.2.0. Актуальные [установка](QUICK_START.md), [совместимость](COMPATIBILITY.md), [управление](SETTINGS.md).

# Validation first — supersedes the earlier milestone ordering

## 1. RTX 5070 compatibility

RTX 5070 is the planned hardware target, never a support claim inferred from its
name. Official NR support and community runtime behavior are different things.
The add-on requires an isolated execution report matching GPU name/UUID/driver,
bridge/runtime/shim hashes, a local NGX core override if present, output order and
probe revision. This is local regression evidence, not a signed attestation or
an audit of every transitive driver dependency. Native Cycles selectors can still
be configured outside the add-on; this gate is not a process-wide security policy.
Multiple NVIDIA GPUs are rejected by the probe until UUID/LUID routing is added.

## 2. Appearance and speed

NR modifies appearance and consumes GPU time. No acceleration, target FPS or fixed
reuse percentage is promised. The report stores each call's duration, including
the cold first call. These 128x128 measurements are not viewport FPS predictions.
Measure Cycles + copies + NR + presentation at the user's resolution separately.
Super Resolution and Frame Generation remain separate, unimplemented features.

## 3. Ordinary Blender remains an experimental preview option

The native Cycles integration requires a patched build. That does not mean all
viewing of NR output requires a patch: a separate window processor such as
[Magpie Experimental](https://github.com/SAOG0721/Magpie) can process captured
application content. Its operation with this user's Blender/5070 is not tested.
It can affect UI and text, has estimated rather than full engine motion, and does
not write the processed image into Blender's final render. No such capture backend
is bundled or silently installed by this project.

## 4. History and motion

Native 0.5.0 forces Reset=1 for every evaluation. This deliberately removes
cross-frame accumulation: camera-only motion is insufficient for moving objects
or multiple views. Calls are serialized and initialization leases are counted,
so one viewport cannot shut down the bridge while another still owns a lease.
Changing runtime/device/channel settings while a lease exists is refused.
Missing guide inputs are uploaded as zeroes, not uninitialized textures.

This is a conservative independent-frame mode, not complete temporal rendering.
Per-context histories, object/deformation motion, camera-cut/seek/discontinuity
tracking and a moving-scene stability test remain required before temporal mode.

## 5. Color

RGB/BGR order is explicit and part of the receipt. The chart rejects swapped
dominant channels and non-finite/negative/incomplete output. Native code rejects
non-finite output before passing it back to Cycles.

The existing Reinhard/sRGB transform and highlight cap are explicitly experimental:
they are not a certified reversible HDR/EXR workflow. Users must review the probe
images and acknowledge that limitation before selecting native NR. The probe saves
raw RGB float32 output alongside clipped display PPM previews. Blender alpha is
copied separately by the Cycles patch; premultiplication and HDR behavior still need
real-scene tests. Do not replace a validated production master with this output.

## 6. Test before integration

The separate worker calls the actual native API on a 128x128 color chart, on a
different image, and on the original chart again. It rejects failures, invalid
pixels, unchanged output, swapped channels and nonrepeatable A/B/A results. The
parent rejects nonzero process exits and kills the worker after 120 seconds.
Native process isolation does not isolate a GPU driver reset from the desktop.

In Blender: approve the trusted runtime in Advanced, press Test Runtime, inspect
the reported directory, then Enable DLSS. It works for probing from stock Blender
too; Enable DLSS still requires the patched Cycles backend.

Outside Blender, with ordinary Windows Python and already built native DLLs:

```powershell
python addon/cycles_dlss5/probe.py --runtime C:\DLSS\runtime --bridge C:\DLSS\dlss5nr_bridge.dll --output C:\DLSS\test-001 --order RGB --trust-runtime
```

The output directory must be new. A report cannot certify HDR, arbitrary scenes,
animation, viewport integration, or performance. First obtain this small execution
result, then test real stills and motion, then package a validated Blender release.
Current workspace tests validate the Python rejection rules only; no Windows/RTX
execution result is available here.
