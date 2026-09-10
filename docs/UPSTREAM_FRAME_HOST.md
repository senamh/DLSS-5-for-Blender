> Архив предыдущих экспериментов. Не инструкция для 0.2.0. Актуальные [установка](QUICK_START.md), [совместимость](COMPATIBILITY.md), [управление](SETTINGS.md).

# Cycles frame input for the existing Feeder host

The next integration stage reuses upstream `jlrouzies-fr/DLSS5-Feeder` host,
pinned at d69d9174ef055f95a657750db814c93ac1ad6c1d. The file adapter adds input
upload/output readback and leaves upstream NGX creation/evaluation, ReShade and
RenoDX loading in place. No custom color filter or neural model is introduced.

## Data path

1. `export_cycles_guides.py`: actual Cycles multipart EXR plus `display.png`,
   saved using Blender's own display transform and scene view settings.
2. `prepare_frame_payload.py`: explicitly selected view-layer Depth and Vector,
   normal device-depth conversion, byte-exact display color packaging.
3. `patch_upstream_frame_host.py` and `native/upstream_host/frame_mode.h`: add
   `--frame WIDTH HEIGHT DIRECTORY` and `--validate-frame WIDTH HEIGHT DIRECTORY`
   to the existing upstream host executable.
4. File mode uploads RGBA8, R32F depth and RG16F static motion; calls upstream
   `CreateFeature` and `Evaluate` with history reset; writes `ngx_output.rgba8`.

For an actual GPU run, the host needs the compatible ReShade `dxgi.dll`, RenoDX
addon and NVIDIA runtimes beside it, as required by upstream. These proprietary
binaries are not distributed by this repository. Require an independent RenoDX
log confirmation of successful feature 18 evaluation before calling its output
DLSS 5: a successful NGX call alone is insufficient. No automatic installation or
update of the user's working preview occurs in this workflow.

## Verified and outstanding

Cloud build 34234185674 rendered the input in official Blender 5.2.1, packaged
true depth, and successfully compiled the adapted Windows host. The executable
accepted a 128x96 Cycles payload and rejected truncated depth without initializing
GPU/NGX. The initial workflow was marked failed because PowerShell propagated the
expected rejection's exit code; the test harness was corrected separately, with
artifact reuse rather than another Blender render/compile.

The GPU upload/evaluate/readback path is **compiled but not GPU-tested**. This is
not a verified DLSS render release. The addon now has a manual payload command;
automatic F12 export/processing remains unfinished. Native graphics resource transitions still require validation with
the target driver/runtime.

Initial limits: opaque sRGB display output, one Combined layer, static Vector
pass, dimensions 96..4096 on each side. Nonzero animation vectors and transparency
are explicitly rejected. Input/output are display-referred SDR, not an HDR EXR
round-trip. Interactive viewport transport and temporal evaluation are separate
unfinished work; this file mode only establishes a still-frame integration path.

## Checkpoint: automated GPU evidence gate

The compiled adapter passed cloud input validation (run 34234555278).
The new `frame-host-gpu.yml` reuses artifacts from run 34234185674, runs five
result-gate unit tests in the cloud, then schedules an isolated Windows RTX test.
It verifies hashes of the previously installed runtime set and uses a fresh temp
directory. It does not install over Blender or change the user's scene.

A successful process or SR evaluation alone is rejected. Acceptance requires a
correctly sized output and an explicit `inline feature 18 evaluation succeeded`
message in this invocation's log. Evidence includes raw-byte-preserving before
and after PNGs, RGB difference metrics, runtime logs and GPU/driver details.
These checks confirm invocation, not perceptual quality or animated stability.

Pending: run this path on RTX 5070; review the image pair; validate moving guides;
integrate F12 and the interactive viewport. This static SDR test is not a finished
interactive addon. A queued job does not count as a successful GPU test.

## Manual addon command

In extension preferences, set **Frame Host** to the adapted
`dlss5-feed-host64.exe` and **Preview Runtime Folder** to the existing tested
preview installation. In Render Properties choose **Process Cycles Frame Payload**
and select `payload.json` produced by the guide export/preparation scripts.
The command currently requires that export; it does not create guides from F12.

The addon copies only input files and the hash-checked runtime set into a fresh
temporary directory. Escape cancels the child process; a 60-second host timeout
is enforced. Successful exit without explicit Feature 18 evidence is rejected.
Accepted output appears as the packed image **DLSS Verified Cycles Frame**;
select it in Image Editor and use Image > Save As. It is display-referred sRGB SDR,
so a second scene view transform is disabled. Original Render Result is preserved.
No automatic export, animation, HDR or live viewport integration is claimed.

## Local frame-host test (2026-09-09)

`scripts/test_local_frame_host.py` exercised the addon's `FrameJob` with the
SHA-256-verified host and Cycles payload from run 34234185674, using the runtime
set from the existing preview installation in an isolated temporary directory.
The 128x96 invocation returned exit code 0 and the fresh RenoDX log confirmed:
`inline feature 18 evaluation succeeded (count=1, NR input 128x96 (guides 128x96), output 128x96 [native])`.
Mean absolute RGB difference was 0.4370659722 on the 8-bit scale, with 16112
changed RGB channels. Input SHA-256:
`2828e302e29cb47c4222c8472f4aa28a2c29cd142ad567120a9d26a17274e646`;
output SHA-256:
`a1c2f51bb54b3ba6e7ed9f7a75b1d7630a2f5794a736bc008eba3224e9064ecc`.
The pair is a tiny, dark test scene; it does not establish perceptual improvement.
This tests the addon's job implementation, not the interactive operator or F12.
The earlier untested-GPU notes above describe the prior cloud checkpoint.
