# Cycles integration: measured progress

Date: 2026-09-09. Development prototype, not a released addon update.

## Completed

- Audited final_render.py: released workflow uses display PNG, constant depth,
  zero motion, and a new host process per evaluation.
- Added run_cycles_prototype.py and render_cycles_prototype.py: separate factory
  Blender process, auto-execution disabled, multilayer Cycles EXR export,
  actual camera-projected Z, pinned runtime validation, NR evaluation and logs.
- Single-frame mode explicitly records that source vectors are not consumed.
  The original four-component Vector pass remains in passes.exr.
- Added host-input validation for nonfinite/out-of-range depth and unsupported
  motion. All 66 unittest checks passed.

## Measured GPU results

Both experiments used Blender 5.2.1 and the existing digest-verified runtime.
Evidence is under the workspace's evidence directory.

| Scene | Resolution | Evidence directory | NR confirmed | Mean RGB difference / 255 |
| --- | --- | --- | --- | --- |
| Blender factory scene | 249 x 140 | cycles-prototype-default-2 | Yes, feature 18 log | 1.164 |
| Cozy Kitchen, Nicole Morena | 504 x 475 | cycles-prototype-kitchen-2 | Yes, feature 18 log | 6.725 |

Cozy Kitchen source: https://download.blender.org/demo/splash/blender-3.5-splash.blend
License: CC-BY-SA, per the previously downloaded SOURCES.json. Output is a
modified test render. Original .blend was not saved or edited.

Results retain before.png, after.png, passes.exr, metadata, payload checksums,
console/ReShade logs and report.json. Difference measures change, not quality.
Visual inspection shows texture/detail and local shading changes; this is not
proof of the desired YouTube quality or of depth improving the network output.

## Current limitations and corrections to the earlier plan

- Native HDR is NOT verified. The current host consumes display sRGB RGBA8.
  Merely allocating RGBA16F does not establish a supported scene-linear model
  contract. The legacy bridge's HDR_TRANSFER mode is a color-transfer technique,
  not evidence of native HDR inference.
- Depth is supplied to the host. Controlled ablation on two scenes found
  byte-identical output for actual, constant-far and constant-near depth in
  reset=1 still mode. This does not establish its role in temporal processing.
- Temporal accumulation is NOT verified. Source motion is retained for research;
  it is deliberately not claimed as an implemented temporal pipeline.
- Prototype exports with compositor, sequencer, border, multiview and motion blur
  disabled in a disposable scene. It must not become the production render button
  without preserving the user's output semantics or explicitly rejecting unsupported
  configurations before rendering.
- OpenEXR 3.4.15 was installed in workspace research-deps for the external Python
  test harness. It is not installed in Blender or bundled in the addon.
- No new release/installation or GitHub publication was performed.

## Next engineering checkpoints

1. Completed: compare actual vs neutral depth with identical color and settings.
2. Establish supported input/output color formats with isolated runtime probes.
3. Integrate same-render guide capture and a persistent process, with cancellation
   and result ownership independent of Blender UI redraws.
4. Validate Vector channel, sign, scale, origin and frame correspondence on known
   object/camera motion before enabling history.
5. Connect the verified path to file-only final rendering, then animation and
   interactive preview. Keep the previous working path available until regression
   tests and visual checks pass.

## Reproduce

Use an external Python with NumPy, Pillow and OpenEXR:

```text
python scripts/run_cycles_prototype.py --blender "PATH/TO/blender.exe" --blend "PATH/TO/scene.blend" --output "NEW/EVIDENCE/DIRECTORY" --long-side 512 --samples 8
```

Runtime discovery uses the existing runtime_setup resolver; optional --runtime
and --host override it. This command never installs the addon. Tests deliberately
use reduced resolution/samples; those overrides are not production output rules.

## Controlled depth experiment (second development step)

Added scripts/compare_cycles_depth.py. Each case starts a fresh host, keeps
Color and Motion bytes unchanged, uses the same default settings and reset=1,
and requires an explicit feature-18 success from that run. The actual-depth
case is repeated to check reproducibility. Neutral replacements are recorded
as experimental replacements, not mislabelled actual Cycles depth.

Eight GPU evaluations passed: actual, actual-repeat, far=1, near=0 on each of
Cozy Kitchen and the factory scene. All three comparisons per scene were
byte-identical, with max and mean RGB difference zero. Evidence:

- evidence/cycles-depth-ablation-kitchen/report.json
- evidence/cycles-depth-ablation-default/report.json

This refutes the earlier expectation that adding Z alone would improve this
still-frame path. It does not prove depth is ignored by every feature-18 model
or with nonzero motion/history. No temporal or HDR claim follows from this test.
Do not add a costly second depth render to the production button based on these
results. Next prioritize persistent session/color-contract investigation and
validated motion correspondence. The interface integration must follow evidence.

All 69 unit tests passed after adding ablation metric checks. The latest script
also records runtime and host checksums for future runs; the first two ablation
reports predate that metadata addition (FrameJob verified the pinned runtime
hashes in all eight runs).

## Persistent native session (third development step)

The earlier stock_worker already retained its C++ DLL and NGX session, but
hardcoded Natural/style=1 for every evaluation. It is a different backend from
the currently active RenoDX frame host. Updated it to validate and forward the
same scene style fields, default to BALANCED, and report PID, GPU, native
settings and reset status. The legacy stock caller now publishes settings on
each frame before its request. Added strict request sequence validation.

Added scripts/benchmark_native_session.py. Tested six evaluations in one process
on RTX 5070 using installed bridge version 0.5.0-independent-frames:

| Input / settings | Seconds |
| --- | --- |
| A, default (initialization included) | 1.093 |
| A repeated | 0.031 |
| B (horizontally mirrored input) | 0.031 |
| A after B | 0.031 |
| A, intensity=0 | 0.156 |
| A, intensity=1 restored | 0.172 |

All default A float arrays were byte-identical, including after another input
and a setting change. Intensity=0 changed the result. Alpha was preserved.
These are small-frame (504x475) processing/file-exchange times, not Cycles render
times or Blender viewport FPS. Changing settings rebuilds the native feature.

Evidence: evidence/native-session-kitchen/report.json and output-0..5.npy.
The report includes actual bridge/runtime/shim hashes. This direct DLL backend
does not use RenoDX's feature-18 log: success is established through the native
process return, finite output, bridge identity and parameter-response checks.
It is not yet established as visually equivalent to the active RenoDX pipeline.

No temporal history was enabled (reset=1), no native HDR was established, and
the primary final-render button has not switched backend. Before switching it,
compare colors/results between backends and implement session lifecycle, error
recovery, cancellation and packaging. All 72 unit tests passed.

## Session lifecycle (fourth development step)

Added experimental NativeSession, not wired into the primary render button.
It owns one subprocess, serializes submissions, verifies sequence/PID/settings,
input/output SHA256, alpha, shape and finite float output before publication.
Worker output is now atomically replaced. Timeout, invalid receipt and worker
exit invalidate the session; cancellation terminates it. Recovery requires a
new session, preventing late results from an old worker being reused.

GPU lifecycle smoke test passed on RTX 5070 with the official Cozy Kitchen
504x475 input: repeated frames matched in the same PID, overlapping submission
was rejected, cancellation terminated the worker, deliberate worker crash was
detected, and a fresh session produced byte-identical output. First round trip
1.297 s; warm repeat 0.078 s; restart 1.125 s (no Cycles rendering included).
Evidence: evidence/native-session-lifecycle-2/report.json. Reproduce with
scripts/smoke_native_session.py --image INPUT --bridge DLL --runtime DIR --output NEW_DIR.

An exploratory comparison of the earlier native output-0.npy (sRGB encoded,
rounded to 8-bit) against the RenoDX kitchen after.png found mean RGB absolute
difference 1.788/255, p95 5/255, max 62/255. This is NOT visual equivalence or
a quality improvement: keep the production backend unchanged pending visual
validation and integration testing. HDR and temporal accumulation remain unproven.
The unit suite now contains 76 passing tests, including stale receipt rejection
and timeout handling. No installed addon/package was replaced during this step.

## Reproducible color comparison (fifth development step)

Added scripts/compare_native_color.py with source hashes, alpha checks, out-of-range
counts, native PNG and a labeled comparison sheet. Evidence is saved under
evidence/native-color-kitchen. This uses existing GPU outputs, not a new GPU run.
The sRGB conversion round-trips all 256 byte values in its unit test; alpha is
not gamma transformed. All 79 unit tests pass.

On Cozy Kitchen, 2.691% of pixels differ by more than 8/255 in at least one RGB
channel between backends. Native output has no out-of-range RGB values and
identical alpha. Visual inspection of the comparison sheet found broadly similar
warm colors and composition, with local differences around pumpkin, edges and
small objects. No gross channel swap or vertical flip is visible. This single
small image does not establish quality parity, and the comparison cannot isolate
the runtime/preprocessing cause of local differences. Do not claim that sRGB
round-trip validation explains all backend differences.

Next integration gate: test the session using Blender's bundled Python and an
official scene at higher resolution, then expose a clearly experimental opt-in
path with existing output settings/cancellation preserved. Production remains
RenoDX; no new UI options or installed addon changes in this step.

## Blender worker / larger official scene (sixth development step)

Extended smoke_native_session.py with --blender to launch the worker through
Blender's bundled Python instead of the external development Python, and retain
output.npy for color comparisons. No Pillow or extra Python packages are needed
inside the worker; Pillow remains a dependency of the external test harness.

Rendered the unchanged official Cozy Kitchen source in background Cycles at
16 samples, requested long side 1024. Blender's integer percentage produced
1008x950 pixels. RenoDX feature-18 evaluation succeeded. Evidence:
evidence/cycles-prototype-kitchen-1024 (render log, passes, payload and images).

Blender-hosted NativeSession passed repeat/PID checks, overlapping submission
rejection, cancellation, intentional crash detection and byte-identical recovery
on RTX 5070. First round trip 3.235 s, warm repeat 0.328 s, recovery 2.031 s.
These timings exclude Cycles rendering and are not interactive viewport FPS.
Evidence: evidence/native-blender-kitchen-1024/report.json. The comparison script
also produced evidence/native-color-kitchen-1024 with both outputs and hashes.
All 79 unit tests still pass. This validates the background worker, NOT the
interactive Blender panel/timers, final output integration or other GPUs.
Production addon and installed files remain unchanged; next is opt-in integration
with explicit runtime verification and retained production fallback.

## Opt-in adapter integration (seventh development step)

Viewport and final-render job creation now share create_job. Default remains
RenoDX. In addon preferences > Advanced, enable “Постоянная сессия NR (эксперимент)”
and explicitly select Native Bridge DLL and NVIDIA NGX Runtime. Stop/restart
preview after changing this setting. Disable it and restart preview to restore
RenoDX. Errors stop processing; there is no silent backend substitution.

NativeFrameJob copies only the three pinned, previously tested binaries into a
private directory and verifies SHA256 before starting Blender. It adapts the
existing prepare/start/poll/finish/close interface, preserving the viewport's
session reuse and existing final output publication. It accepts only image-only
far-depth/zero-motion payloads, not actual Cycles depth. Frames remain SDR.
Final jobs are closed after publication, so warm reuse currently benefits
viewport updates, not separate final render operations.

Important: the RenoDX runtime hash and native runtime hash differ. The observed
color differences cannot be attributed solely to the host implementation.
Quality parity is not established and this mode is deliberately opt-in.

GPU smoke test scripts/smoke_native_adapter.py passed at 1008x950 with a private
pinned runtime under Blender Python: same PID, byte-identical repeated PNG,
publication and cleanup. Evidence: evidence/native-adapter-kitchen-1024.
Interactive panel, timer/cancel interaction and output-format integration still
need Blender UI testing. No installed addon or release archive was updated.

## Final integration / 0.2.2 candidate

Fixed preflight routing in render operator, render handler, viewport start and
setup-check operator: native mode no longer requires the unrelated RenoDX host.
The native preflight verifies the pinned hashes, while the adapter separately
verifies private copies immediately before execution.

scripts/smoke_native_final.py passed in background Blender 5.2.1 / RTX 5070:
factory Cycles render, FILM settings snapshot despite a later edit, transparent
PNG saved to the configured disk destination, no change to scene output/color
settings, overwrite rejection and cancellation preserving the prior good image.
Evidence: evidence/native-final-integration/report.json. Tests call the render
handlers and operators programmatically; this is not a physical UI click test.

Existing smoke_output_settings.py and smoke_menu_ownership.py also passed:
seven SDR encoders, output folder operator and single registration/handler owner.
Prepared 0.2.2 addon-only candidate; native DLLs remain separate prerequisites.
No installed addon replaced; no GitHub publication performed.

## ZIP isolation and native GUI automation

scripts/smoke_addon_zip.py extracts the distributed addon-only ZIP into a fresh
temporary module directory, verifies ZIP integrity and safe paths, and runs the
complete native final integration test against that exact imported directory.
The original 0.2.2 ZIP passed; evidence/addon-zip-022/report.json records its hash.
No user preferences were saved and no user addon installation was replaced.

Extended smoke_unified_viewport.py with explicit --native and --evidence options.
An isolated factory-startup GUI Blender process passed the native test on RTX 5070:
actual VIEW_3D draw, stable idle, style change, mesh-edit refresh, folder operator,
file-only render, shared style settings, progress stages, Image Editor result,
no new viewport, and repeated Show Result without a duplicate window.
Evidence: evidence/native-viewport-gui/report.json and stdout.log.
Operators were dispatched with Blender context overrides, not physical mouse
clicks. This does not validate every shortcut, visual quality or other hardware.
The test closed its own Blender process. All 81 unit tests also pass.
