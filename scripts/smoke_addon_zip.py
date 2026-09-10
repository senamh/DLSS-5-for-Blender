"""Test the distributed ZIP in an isolated module directory; no user installation."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('zip', 'blender', 'bridge', 'runtime', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'zip_sha256': hashlib.sha256(args.zip.read_bytes()).hexdigest(),
              'interactive_ui_tested': False, 'user_installation_modified': False}
    with tempfile.TemporaryDirectory(prefix='dlss5-zip-test-') as folder:
        module = Path(folder)/'cycles_dlss5'
        module.mkdir()
        with zipfile.ZipFile(args.zip) as archive:
            if archive.testzip() is not None:
                raise ValueError('Corrupt ZIP')
            for name in archive.namelist():
                target = (module/name).resolve()
                if not target.is_relative_to(module.resolve()):
                    raise ValueError('Unsafe ZIP path')
            archive.extractall(module)
            report['files'] = archive.namelist()
        command = [str(args.blender), '--background', '--factory-startup', '--disable-autoexec',
                   '--python-exit-code', '1', '--python',
                   str(Path(__file__).with_name('smoke_native_final.py')), '--',
                   str(args.bridge.resolve()), str(args.runtime.resolve()),
                   str((args.output/'render').resolve()), folder]
        with (args.output/'blender.log').open('w', encoding='utf-8') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        report['exit_code'] = result.returncode
        report['passed'] = result.returncode == 0 and (args.output/'render/report.json').is_file()
    (args.output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    if not report['passed']:
        raise RuntimeError('ZIP integration failed; see blender.log')
    print('ZIP integration passed:', report['zip_sha256'])


if __name__ == '__main__':
    main()
