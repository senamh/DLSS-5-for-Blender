import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches" / "blender-v5.2.1-dlss5nr.patch"
PIN = "9e2066aef7ef7e20c142ad7bd3303138a4304c93"


class BlenderPatchTests(unittest.TestCase):
    def test_patch_targets_required_cycles_interfaces(self):
        text = PATCH.read_text(encoding="utf-8")
        for marker in (
            "DENOISER_DLSS5NR",
            "DENOISER_PASS_DEPTH",
            "DENOISER_PASS_MOTION",
            "temporally_stable = false",
            "denoiser_dlss5nr.cpp",
            "denoised_buffer_params",
        ):
            self.assertIn(marker, text)

    def test_scripts_pin_blender_5_2_1(self):
        for name in ("fetch_blender_5_2.ps1", "apply_blender_patch.ps1"):
            self.assertIn(PIN, (ROOT / "scripts" / name).read_text(encoding="utf-8"))

    def test_patch_has_lf_line_endings(self):
        self.assertNotIn(b"\r\n", PATCH.read_bytes())


if __name__ == "__main__":
    unittest.main()

