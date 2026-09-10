import importlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

package = types.ModuleType('_setup_tests')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'addon/cycles_dlss5')]
sys.modules[package.__name__] = package
setup = importlib.import_module('_setup_tests.runtime_setup')
job = importlib.import_module('_setup_tests.frame_job')


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self, folder):
        folder.mkdir(parents=True)
        for name in (*job.RUNTIMES, 'dlss5-feed-host64.exe'):
            (folder / name).write_bytes(b'fixture, not executable')
        return folder

    def test_relocated_packaged_runtime(self):
        for name in ('first', 'другая папка'):
            root = self.root / name
            runtime = self.fixture(root / 'runtime')
            host, found = setup.resolve(addon=root, environ={}, system='win32')
            self.assertEqual(found, runtime)
            self.assertEqual(host.parent, runtime)

    def test_explicit_and_environment_paths(self):
        runtime = self.fixture(self.root / 'chosen')
        self.assertEqual(setup.resolve(str(runtime), environ={}, system='win32')[1], runtime)
        self.assertEqual(setup.resolve(environ={'DLSS5_RUNTIME_DIR': str(runtime)}, system='win32')[1], runtime)

    def test_missing_or_incomplete_runtime(self):
        with self.assertRaisesRegex(ValueError, 'не найден'):
            setup.resolve(str(self.root), environ={}, system='win32')

    def test_unsupported_os_is_clear(self):
        for os_name in ('linux', 'darwin'):
            with self.assertRaisesRegex(ValueError, 'Windows'):
                setup.resolve(system=os_name)

    def test_unknown_binary_not_accepted(self):
        runtime = self.fixture(self.root / 'runtime')
        with self.assertRaisesRegex(ValueError, 'Непроверенная'):
            setup.verify_files(runtime / 'dlss5-feed-host64.exe', runtime)
