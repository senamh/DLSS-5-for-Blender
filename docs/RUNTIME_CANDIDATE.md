> Архив предыдущих экспериментов. Не инструкция для 0.2.0. Актуальные [установка](QUICK_START.md), [совместимость](COMPATIBILITY.md), [управление](SETTINGS.md).

# RTX 5070 runtime candidate

As of 2026-09-07, DLSS5oneclick's installer selects the community
`dlssnr-310.8.SF-v2` release for its multi-generation runtime route:

- [Installer selection source](https://github.com/faisalkindi/DLSS5oneclick/blob/main/src/installer.rs)
- [Candidate archive](https://github.com/RankFTW/rhi-repo/releases/tag/dlssnr-310.8.SF-v2)

The archive publisher reports SHA-256
`1da35941894994eb087e017577829e492454e9bae3a6a9397027069ceb74955c`.
This checks download identity, not NVIDIA provenance, safety, licensing or GPU
compatibility. The candidate is not included in our binary distribution.

The archive was downloaded and its SHA-256 matched on 2026-09-07. It contains one
`nvngx_dlssnr.dll` (165830144 bytes), with SHA-256
`6eb209e764f39872625debd6abaf45e2bb6322f6f270f781f70c059ae30b3927`.
Its PE signature was inspected without loading it. No GPU evaluation was run.

To download just the candidate into a built portable Blender's runtime folder:

```powershell
.\scripts\fetch_runtime_candidate.ps1 -RuntimeDirectory 'C:\Blender-DLSS\runtime'
```

The helper refuses to overwrite an existing model, verifies the archive hash,
extracts only `nvngx_dlssnr.dll`, and writes a download receipt. It never loads
the DLL or marks the runtime as recognized. Keep the caller shim from our build.
Then use Test Runtime in the add-on. A passing isolated test must be followed by
actual Cycles still-render and viewport testing on the target GPU.

## Cycles integration test

After Test Runtime passes, copy its report path from Advanced. From the repository
root, run the following in PowerShell, substituting your built Blender paths:

```powershell
& 'C:\Blender-DLSS\blender.exe' --background --factory-startup --python-exit-code 1 --python scripts/verify_cycles.py -- --runtime 'C:\Blender-DLSS\runtime' --bridge 'C:\Blender-DLSS\dlss5nr_bridge.dll' --probe-report 'C:\path\to\report.json' --output 'C:\DLSS-test-001' --trust-runtime --allow-experimental-color *> cycles-test.log
```

Use a new output directory each time. The script requires a single OptiX GPU,
compares Cycles with and without DLSS on two independently rendered frames,
changes object position and resolution, and saves four 32-bit RGBA EXRs plus
`cycles-report.json`. RGB changes, finite pixels and preserved alpha are checked.
An unchanged chart fails conservatively and needs investigation; it does not prove
incompatibility. Render timings include setup and shader compilation, not viewport
FPS. A successful report is only a functional still-render check, not proof of
HDR fidelity, temporal stability or viewport operation. A nonzero process exit
or missing report is a failure even if some EXRs exist.

`neural-upstream` documents Ada kernel translation, but its inspected repository
does not contain the modified model or a runtime rebuilding tool. Its ReShade
add-on is not a replacement for the NVIDIA model DLL.
