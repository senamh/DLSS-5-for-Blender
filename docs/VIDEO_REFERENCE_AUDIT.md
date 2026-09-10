> Архив предыдущих экспериментов. Не инструкция для 0.2.0. Актуальные [установка](QUICK_START.md), [совместимость](COMPATIBILITY.md), [управление](SETTINGS.md).

# Audit of the Mr PK video reference — 2026-09-08

Reference: https://www.youtube.com/watch?v=aQqS2Qhz2rk
Title: How to Install DLSS 5 in Unreal Engine 5.
The description was retrieved from YouTube player metadata. The full video was
not visually reviewed, so exact slider positions demonstrated in it remain unknown.

## Direct archive evidence

Downloaded the publicly linked archive from:
https://drive.google.com/file/d/1AB_4u3_FxvUtTZdSPSAmcDrFd2GzN_c0/view

Archive SHA256: `ada812f283ac75d4b0ee88cfabd7e763e5cad98424105a99acf9bd256fe387f8`.
No executable, addon or DLL from this archive was loaded or installed.
The current download may differ from what was available when the video was recorded.

| Component | Archive evidence | Our stock addon |
| --- | --- | --- |
| Neural runtime | `streamline/nvngx_dlssnr.dll`, 165840496 bytes | 165830144 bytes, SF-v2 candidate |
| Runtime SHA256 | `4b8d19bc3eff58a084f5eca7489c921501c203450169fb82ff4f649a4482ba05` | `6eb209e764f39872625debd6abaf45e2bb6322f6f270f781f70c059ae30b3927` |
| Consumer | `renodx-dlss5.addon64`, 550912 bytes | Our D3D12 bridge |
| Consumer SHA256 | `a8b5e164cbc3222a5d62bbddf44a2cc68d359b0caf729e55f2877c49e73e9aac` | Built from native source in this repository |
| Other files | ReShade 6.8 installer, SR/FG and Streamline DLLs | No game DLSS hook or Streamline pipeline |

Different hashes prove different files, not necessarily different model weights.
The mod contains a label referencing DLSSNR v310.8.0; that label is not independent
proof of the bundled runtime's exact version or build provenance.

## Confirmed processing differences

1. The mod's embedded shader contains an UpgradeToneMap function. It compares
   original, proxy and neural luminance, applies a two-branch ratio, corrects hue
   in OkLab and blends with the original using TransferStrength. Our bridge instead
   decodes and applies inverse Reinhard to the model's output, then limits overshoot.
2. The mod's embedded codec diagnostic describes soft-clip/sRGB handling for HDR
   tagged by NGX. Our bridge applies Reinhard and sRGB encoding to every input,
   including an already display-mapped viewport capture that was inverse-sRGB decoded.
3. Our worker hardcodes Style=1, Preset=0, Intensity=1, LocalTone=1,
   LocalStructure=1, Skin=-1, AutoMask=0. These settings are not exposed in the stock UI.
   The exact video's settings and the mod's numeric defaults were not recovered.
4. Our bridge supplies zero depth and motion guides and forces Reset=1 every frame.
   The reference is a game DLSS post-pass; equivalence of its actual input buffers
   and reset behavior has not been established from static inspection alone.
5. Our viewport captures display pixels and UI overlays after Blender color management.
   This does not recover the original scene-linear HDR buffers.

Independent open-source cross-check:
https://github.com/Dagherbou/OptiScaler_DLSSNR/tree/dlss-neural-rendering/OptiScaler/dlssnr
Its README explicitly attributes its ratio composition to RenoDX. Its Config.h
defaults Style=0 and Intensity=1. Those are OptiScaler defaults, not verified values
from this video's RenoDX build. This cross-check corroborates a design direction,
not binary/source identity with the video archive.

## What the existing tests do and do not establish

We established runtime execution, finite changed pixels, alpha preservation,
operator operation, worker reuse and viewport drawing. We have not established
equivalent relighting, material reconstruction, HDR fidelity, temporal quality or
visual equivalence with the video. Passing a pixel-change assertion is insufficient
for any of those claims. A primitive cube is also an inadequate visual quality benchmark.

## Next validation gate

Use the same representative scene/frame for all comparisons, including a textured
material, hair/skin or fabric and controlled lighting. Test color handling first,
holding the runtime and model parameters fixed. Test runtime replacement separately
in an isolated process. Add parameter controls only with explicit reinitialization
when create-time settings change. Keep the original image and record the exact
configuration for every comparison. Do not overwrite the user's working installation
until the new path passes execution and visual comparison.

Do not copy embedded shader code without resolving its applicable license; the
audit records behavior and fingerprints, not a redistribution of the binary bundle.
