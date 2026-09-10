"""Package the UI extension only; native Blender/runtime are separate prerequisites."""
from pathlib import Path
import argparse
import zipfile
import importlib
import sys
import types
import ast
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def validate_source(source):
    manifest = tomllib.loads((source/'blender_manifest.toml').read_text(encoding='utf-8'))
    version = tuple(int(n) for n in manifest['version'].split('.'))
    tree = ast.parse((source/'__init__.py').read_text(encoding='utf-8'))
    info = next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'bl_info'
                                                       for t in node.targets))
    if info['version'] != version:
        raise ValueError('Manifest and bl_info versions differ')
    for path in source.glob('*.py'):
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
    return manifest['version']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='ZIP destination (default: project dist directory)')
    parser.add_argument('--private-runtime', type=Path,
                        help='Personal offline transfer only: include your legally obtained tested runtime; never publish this ZIP')
    parser.add_argument('--public', action='store_true',
                        help='Fail if any third-party runtime was requested; use for CI/public releases')
    args = parser.parse_args()
    if args.public and args.private_runtime:
        parser.error('--public cannot be combined with --private-runtime')
    source = ROOT / "addon/cycles_dlss5"
    version = validate_source(source)
    target = args.output or ROOT / f"dist/cycles_dlss5-{version}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    runtime = None
    if args.private_runtime:
        package = types.ModuleType('_package_dlss5')
        package.__path__ = [str(source)]
        sys.modules[package.__name__] = package
        setup = importlib.import_module('_package_dlss5.runtime_setup')
        host, runtime = setup.resolve(str(args.private_runtime), system='win32')
        setup.verify_files(host, runtime)
        names = importlib.import_module('_package_dlss5.frame_job').RUNTIMES
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.iterdir()):
            if path.is_file() and path.suffix in {".py", ".toml"}:
                archive.write(path, path.name)
        archive.write(ROOT / "LICENSE", "LICENSE")
        archive.write(ROOT / 'THIRD_PARTY_NOTICES.md', 'THIRD_PARTY_NOTICES.md')
        archive.write(ROOT / 'docs/QUICK_START.md', 'INSTALL.md')
        archive.write(ROOT / 'docs/COMPATIBILITY.md', 'COMPATIBILITY.md')
        archive.write(ROOT / 'docs/SETTINGS.md', 'SETTINGS.md')
        archive.write(ROOT / 'CHANGELOG.md', 'CHANGELOG.md')
        archive.write(ROOT / 'docs/TESTING_STATUS.md', 'TESTING_STATUS.md')
        archive.write(ROOT / 'docs/RUNTIME_DISTRIBUTION.md', 'RUNTIME_DISTRIBUTION.md')
        if runtime is not None:
            for name in names:
                archive.write(runtime / name, 'runtime/' + name)
            archive.write(host, 'runtime/dlss5-feed-host64.exe')
            archive.writestr('runtime/PRIVATE-TRANSFER.txt',
                            'Personal offline transfer of an existing runtime. Not a public release.\n'
                            'Third-party binaries retain their original licenses; MIT applies only to project source.\n'
                            'Do not publish or redistribute this archive without the required rights.\n')
    print(target)


if __name__ == "__main__":
    main()
