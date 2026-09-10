# DLSS 5 for Blender

Experimental NVIDIA Neural Rendering processing for **stock Blender 5.2**.
Last updated: **September 10, 2026**. Current version: **0.2.2 Experimental**.

## Download and install

### Requirements

- Windows 11 x64.
- Blender **5.2.x**.
- An NVIDIA RTX GPU and a current driver. The RTX 5070 is the only GPU verified
  end to end; see the [compatibility matrix](docs/COMPATIBILITY.md).
- A compatible DLSS NR runtime obtained separately from a source you are
  authorized to use.

### Add-on installation

1. Download [release v0.2.2](https://github.com/senamh/DLSS-5-for-Blender/releases/tag/v0.2.2)
   or the [ready-to-install add-on ZIP](release/cycles_dlss5-0.2.2-public-safe.zip).
2. **Do not extract the ZIP.** Open Blender and go to
   **Edit → Preferences → Add-ons**.
3. Click **Install from Disk**, select
   `cycles_dlss5-0.2.2-public-safe.zip`, and enable **Cycles DLSS 5**.
4. Open the add-on preferences and select the **Runtime directory**. It must contain:

   ```text
   dlss5-feed-host64.exe
   opengl32.dll
   renodx-dlss5.addon64
   nvngx_dlss.dll
   nvngx_dlssnr.dll
   ```

5. Click **Verify installation and GPU**. File validation must pass; actual GPU
   compatibility is confirmed only when an NR frame is processed successfully.
6. Open a scene using **Cycles**, then select **N → DLSS 5** in the 3D Viewport.
   Use **Viewport Effect** for preview or **Render with Effect…** to save a file.

If the add-on cannot find the runtime, select its directory again in Preferences
and restart Blender. Do not copy the DLL files next to `blender.exe`. See the
[Quick Start](docs/QUICK_START.md) for portable installation and troubleshooting.

> **Important:** the public GitHub ZIP does not include proprietary NVIDIA,
> RenoDX, or ReShade runtime binaries and cannot perform real NR by itself.
> Do not publish or sell a personal offline package containing these binaries
> unless you have the required redistribution rights. See
> [Runtime distribution](docs/RUNTIME_DISTRIBUTION.md).

### Personal offline installation (full-runtime package)

This option is only for transferring your own tested runtime between computers
where you are authorized to use it. The private package is named
`cycles_dlss5-0.2.2-personal-full-runtime.zip`. It is not available on GitHub.

1. Install Blender **5.2.x** and the current NVIDIA driver on the destination PC.
2. Copy `cycles_dlss5-0.2.2-personal-full-runtime.zip` to that PC. Do not extract it
   and do not place any DLL files beside `blender.exe`.
3. In Blender, open **Edit → Preferences → Add-ons → Install from Disk** and select
   the complete ZIP.
4. Enable **Cycles DLSS 5**. The add-on automatically discovers the `runtime`
   directory embedded in its own installation.
5. If Blender preferences were copied from another computer, clear the old absolute
   values in **Runtime directory** and **Frame Host** so the embedded files are used.
6. Click **Verify installation and GPU**. A successful file check confirms that the
   package is intact; it does not by itself guarantee that the GPU supports this runtime.
7. Restart Blender, switch the scene render engine to **Cycles**, and open
   **N → DLSS 5** in the 3D Viewport.
8. Click **Viewport Effect** and wait for Cycles capture and NR processing to finish.
   The percentage indicator shows the current operation. The result is applied in
   the same viewport.
9. For final output, click **Render with Effect…**, choose an existing output folder,
   a new filename, and a supported format. Existing files are not overwritten.
10. Click **Show Result** to open the processed frame in a separate Image Editor window.

Troubleshooting the personal package:

- **Runtime not found:** clear copied paths in the add-on preferences, disable and
  re-enable the add-on, then restart Blender.
- **Unrecognized runtime:** the embedded files do not match the pinned SHA-256 values;
  rebuild the personal package from the tested runtime instead of disabling validation.
- **No NVIDIA GPU detected:** install the current NVIDIA driver and confirm that
  `nvidia-smi` can see the RTX GPU.
- **No visible result yet:** wait until both the Cycles capture and the NR worker finish.
  Processing is asynchronous and is not real-time gameplay DLSS.
- **Double processing or a ReShade overlay:** launch stock Blender without an external
  ReShade injection. The add-on manages its own isolated processing path.
- **Unsupported system:** this backend does not support AMD, Intel, Apple, GTX,
  Linux, or macOS.

Do not upload, sell, or redistribute the personal full-runtime ZIP unless you have
explicit rights for every included NVIDIA, RenoDX, and ReShade binary.

[Settings and shortcuts](docs/SETTINGS.md) ·
[Tests and limitations](docs/TESTING_STATUS.md) ·
[Changelog](CHANGELOG.md)

## Features

- Applies the result directly in the current 3D Viewport; no before/after viewport.
  Finished renders open in a separate Image Editor window.
- Asynchronous updates after viewport movement stops, with shared NR settings for
  viewport previews and final renders.
- **Render with Effect…** saves only to a file and provides Blender output settings,
  directory, filename, and format controls.
- Uses the scene camera, resolution percentage, samples, and compositor settings.
- Can process an existing Render Result without rendering the scene again.
- One add-on panel, cancellable processing, progress display, and overwrite protection.
- Runtime/GPU validation and portable paths without a fixed Windows username or
  Steam installation directory.
- Optional persistent experimental NR session in **Preferences → Advanced**.
  It uses a separate pinned native runtime with SHA-256 validation and is disabled
  by default.

## Shortcuts

Place the cursor over the 3D Viewport when using the default Blender 5.2 keymap.

| Key | Action |
| --- | --- |
| F6 | Toggle the viewport effect |
| F7 | Open the render-to-file dialog |
| F8 | Stop NR processing and preview |
| N | Open Blender's standard sidebar |
| F12 / Esc | Standard Blender render / cancel; not reassigned by this add-on |

If F6, F7, or F8 conflicts with another keymap or add-on, the conflicting DLSS
shortcut is skipped. The panel buttons remain available. The old Ctrl+Alt shortcuts
were removed, and this add-on does not use F10.

## Compatibility and honest status

Verified on **Windows 11, Blender 5.2.1 LTS, and GeForce RTX 5070**. Other RTX 50
GPUs are targets but have not been tested individually. RTX 20/30/40 and RTX PRO
are not confirmed with the pinned runtime. AMD, Intel, Apple, GTX, Linux, and macOS
are not supported by this NR backend. See the [compatibility matrix](docs/COMPATIBILITY.md).

The primary RenoDX path confirms an NVIDIA feature 18 call. The experimental native
path verifies the DLL output and receipt for a specific frame. Both are currently
**image-only consumers**, not native Cycles/game integrations: they do not provide
real motion/depth guides or temporal history. This is not Frame Generation and does
not accelerate the Cycles renderer itself.

HDR/EXR, animation, and multiview are not supported. Internal processing is 8-bit
sRGB SDR even when saving a 16-bit PNG or TIFF. Matching YouTube demonstrations or
improving every frame is not guaranteed.

In one persistent-session test using the 1008×950 Cozy Kitchen scene, the first
response took 3.235 seconds and the repeated response took 0.328 seconds. This is
**not an FPS measurement** and excludes Cycles rendering, viewport capture, and the
initial DLL copy. The Natural face tests noticeably modify skin, eyes, and lips;
this may look more realistic but may also alter original details or identity.
See [test methodology and limitations](docs/TESTING_STATUS.md).

## Development

```powershell
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -q
python scripts/package_addon.py --public --output dist/cycles_dlss5-0.2.2.zip
```

[Architecture](docs/ARCHITECTURE.md) · [Roadmap](docs/ROADMAP.md)

Experiments involving a patched Blender build or screen-level ReShade are archived.
Do not use their instructions instead of the Quick Start. Building Blender is not
required to install the add-on, and a successful ZIP build does not replace GPU testing.

## License

Original project code is MIT licensed. Blender is GPL licensed. NVIDIA, ReShade,
RenoDX, and other dependencies retain their own licenses. This is an independent
community project by **Strela Industries**, not an official or certified NVIDIA or
Blender integration. See [Third-party notices](THIRD_PARTY_NOTICES.md).
