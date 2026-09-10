# Third-party notices

## Current addon and worker

The current addon uses the DLSS5-Feeder host by Jean-Laurent ROUZIES (MIT), pinned
to d69d9174ef055f95a657750db814c93ac1ad6c1d with this repository's frame adapter.
Upstream notices include portions derived from NIGos' dlss5-dx11-bridge (MIT).
See https://github.com/jlrouzies-fr/DLSS5-Feeder for the complete upstream notices.

ReShade, RenoDX and NVIDIA NGX/DLSS runtimes are external dependencies; this
project's MIT license does not relicense them. Public addon packaging and GitHub
artifacts exclude proprietary runtime binaries. The optional private offline
packager copies an existing user-owned runtime for personal transfer only; it
does not grant redistribution rights. Retain suppliers' licenses and comply with
their terms. The project does not download, patch or bypass licensing checks in
NVIDIA binaries as part of normal addon setup.

## blender-dlss5-denoiser

The initial Cycles patch and Windows bridge are derived from
[`alanmsyarif/blender-dlss5-denoiser`](https://github.com/alanmsyarif/blender-dlss5-denoiser),
revision `2c2448d7a64a5df5288024e5cef158d7fbe62e55`, under the MIT License.

The port keeps the original SPDX declarations in Blender-derived files. Changes
to Blender source must be distributed under a GPL-compatible license. NVIDIA
runtime binaries are not part of this repository and must not be committed.
# Runtime binaries are not covered by this project's MIT license

The public addon archive does not include `nvngx_dlssnr.dll`,
`renodx-dlss5.addon64`, ReShade binaries, or caller-validation shims.
Possession or a matching SHA-256 does not grant redistribution rights.
See `docs/RUNTIME_DISTRIBUTION.md` before preparing any binary package.
