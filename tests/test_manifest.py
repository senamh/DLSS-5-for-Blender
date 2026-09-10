from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).parents[1]


class ManifestTests(unittest.TestCase):
    def test_manifest_targets_blender_52(self):
        manifest_path = ROOT / "addon" / "cycles_dlss5" / "blender_manifest.toml"
        with manifest_path.open("rb") as handle:
            manifest = tomllib.load(handle)

        self.assertEqual(manifest["id"], "cycles_dlss5")
        self.assertEqual(manifest["blender_version_min"], "5.2.0")
        self.assertEqual(manifest["type"], "add-on")


if __name__ == "__main__":
    unittest.main()

