"""Source contracts only: these tests do not execute PowerShell or MSVC."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WindowsBuildContractTests(unittest.TestCase):
    def test_backend_and_import_check_are_required(self):
        script = (ROOT / 'scripts/build_portable_windows.ps1').read_text()
        for marker in ('-DWITH_CYCLES_DLSS5_NR=ON', '-DWITH_CYCLES_DEVICE_OPTIX=ON',
                       '--python-exit-code', 'assert _cycles.with_dlss5nr',
                       '9e2066aef7ef7e20c142ad7bd3303138a4304c93'):
            self.assertIn(marker, script)

    def test_no_destructive_cleanup_or_source_update(self):
        script = (ROOT / 'scripts/build_portable_windows.ps1').read_text()
        self.assertNotIn('Remove-Item', script)
        self.assertNotIn('reset --hard', script)
        self.assertIn('[guid]::NewGuid()', script)
        self.assertIn("'submodule', 'update', '--init', '--checkout', 'lib/windows_x64'", script)

