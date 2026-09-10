import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('release_packager', root/'scripts/package_addon.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ReleaseTests(unittest.TestCase):
    def test_real_source_versions_and_syntax_match(self):
        self.assertEqual(module.validate_source(root/'addon/cycles_dlss5'), '0.2.2')

    def test_mismatched_version_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/'blender_manifest.toml').write_text('version = "0.2.2"')
            (path/'__init__.py').write_text('bl_info = {"version": (0, 2, 1)}')
            with self.assertRaises(ValueError):
                module.validate_source(path)

    def test_public_and_private_runtime_are_mutually_exclusive(self):
        with patch.object(sys, 'argv', ['package_addon.py', '--public', '--private-runtime', 'runtime']):
            with self.assertRaises(SystemExit):
                module.main()
