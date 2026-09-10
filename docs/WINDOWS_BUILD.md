> Архив предыдущих экспериментов. Не инструкция для 0.2.0. Актуальные [установка](QUICK_START.md), [совместимость](COMPATIBILITY.md), [управление](SETTINGS.md).

# Experimental Windows build

This is a build procedure, not a verified release. Windows execution and RTX 5070
neural-rendering tests remain outstanding. No NVIDIA runtime is downloaded or
bundled. Runtime availability and Ada compatibility are independent blockers.

## Prerequisites

- Windows x64, Visual Studio 2022 Desktop development with C++ and Windows SDK.
- Git with Git LFS, CMake and Python available on PATH.
- NVIDIA OptiX SDK installed separately; CUDA toolkit if required by the selected
  Blender kernel build. The pinned Blender CMake checks report missing versions.
- Sufficient disk space for Blender's source, precompiled libraries and build.

From the repository root in PowerShell:

```powershell
.\scripts\fetch_blender_5_2.ps1
.\scripts\build_portable_windows.ps1 -OptixRoot 'C:\SDK\OptiX' -Jobs 4
```

The script keeps Blender's pinned source revision, fetches its recorded Windows
library submodule and LFS files, applies the patch, builds both native DLLs and
Blender, and checks `_cycles.with_dlss5nr` in a separate background process.
It creates a new output directory under `dist` without deleting earlier builds.
The smoke check does not establish DLL initialization or image-processing success.

## First hardware test

1. Start the output directory's `Start-DLSS-Blender.cmd`.
2. The bundled panel is enabled automatically for this session. The ZIP is
   available separately for manual installation in another patched build.
3. Obtain a compatible, trusted runtime separately and place `nvngx_dlssnr.dll`
   in `runtime`. The built caller shim is already in `runtime/caller`.
4. In the add-on, select that runtime folder and `dlss5nr_bridge.dll`, inspect
   diagnostics, and explicitly approve an unknown runtime only if you trust it.
5. Run Test Runtime, review its chart images and experimental-color setting,
   then configure the session and test a disposable Cycles scene, first a still,
   then rendered viewport. Do not use valuable unsaved work for native tests.
6. Record driver version, runtime hash, GPU, errors and before/after output.

The launcher enables only the panel; neural runtime loading requires Test Runtime
and Enable DLSS. Reconfigure paths each session and restart after replacing DLLs.
The build runs registration, disable and reload checks in the actual installed
Blender and saves `blender-smoke.json`. This report explicitly excludes neural
rendering. Directly starting `blender.exe` does not run the panel launcher.
No FPS, temporal stability, Ada compatibility or final-image correctness is
promised until these tests pass. Before distributing Blender binaries, accompany
them with their corresponding source and required license material.
