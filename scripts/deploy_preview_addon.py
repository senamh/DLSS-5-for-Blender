"""Update only the Python UI of an explicitly selected existing preview; keep backups."""
from pathlib import Path
import hashlib
import shutil
import sys
import tempfile
import runpy

source = Path(__file__).resolve().parents[1]
runtime = Path(sys.argv[1]).resolve()
if not all((runtime / name).is_file() for name in ('blender.exe', 'start_preview.py', 'renodx-dlss5.addon64')):
    raise ValueError('Not an existing DLSS Preview installation')
destination = runtime / 'dlss5_addons' / 'cycles_dlss5'
backup = Path(tempfile.mkdtemp(prefix='dlss5-ui-backup-'))
shutil.copy2(runtime / 'start_preview.py', backup / 'start_preview.py')
if destination.exists():
    shutil.copytree(destination, backup / 'cycles_dlss5')
destination.mkdir(parents=True, exist_ok=True)
for path in (source / 'addon/cycles_dlss5').iterdir():
    if path.is_file() and path.suffix in ('.py', '.toml'):
        shutil.copy2(path, destination / path.name)
shutil.copy2(source / 'scripts/start_preview.py', runtime / 'start_preview.py')
migrate = runpy.run_path(str(source / 'addon/cycles_dlss5/preview_controls.py'))['migrate_bindings']
config_path, preset_path = runtime / 'ReShade.ini', runtime / 'ReShadePreset.ini'
config, preset = migrate(config_path.read_text(encoding='utf-8-sig'), preset_path.read_text(encoding='utf-8-sig'))
for path, text in ((config_path, config), (preset_path, preset)):
    shutil.copy2(path, backup / path.name)
    path.write_text(text, encoding='utf-8')
print('Removed DLSS bindings from F10, F7 and F6; F8 retained as overlay escape')
for name in ('README-preview.txt', 'READ-ME.txt'):
    target = runtime / name
    if target.exists():
        shutil.copy2(target, backup / name)
    shutil.copy2(source / 'scripts/README-preview.txt', target)
if len(sys.argv) > 2:
    host = Path(sys.argv[2]).resolve()
    if hashlib.sha256(host.read_bytes()).hexdigest() != '516af8d981a488129f41d68edf1badc4d65f98d246aafd5d512edf1e7cc7f36c':
        raise ValueError('Frame host differs from the locally verified build')
    host_target = runtime / 'frame-host/dlss5-feed-host64.exe'
    if host_target.exists():
        shutil.copy2(host_target, backup / 'dlss5-feed-host64.exe')
    host_target.parent.mkdir(exist_ok=True)
    if host != host_target.resolve():
        shutil.copy2(host, host_target)
    print('Installed verified frame host:', host_target)
if len(sys.argv) > 3:
    extension = Path(sys.argv[3]).resolve()
    import tomllib
    with (extension / 'blender_manifest.toml').open('rb') as handle:
        manifest = tomllib.load(handle)
    if extension.name != 'cycles_dlss5' or manifest.get('id') != 'cycles_dlss5':
        raise ValueError('Not the existing cycles_dlss5 extension')
    shutil.copytree(extension, backup / 'installed_extension')
    for path in destination.iterdir():
        if path.is_file() and path.suffix in ('.py', '.toml'):
            shutil.copy2(path, extension / path.name)
    print('Updated existing extension:', extension)
print('Installed addon:', destination)
if len(sys.argv) > 4:
    launcher = Path(sys.argv[4]).resolve()
    previous = launcher.read_text(encoding='utf-8-sig')
    if launcher.name != 'Blender-DLSS5-5070.cmd' or not any(token in previous for token in
            ('DLSS-Blender', 'Unified addon viewport/render path')):
        raise ValueError('Not the known DLSS launcher; preserve it and select explicitly')
    shutil.copy2(launcher, backup / launcher.name)
    shutil.copy2(source / 'scripts/Blender-DLSS5-5070.cmd', launcher)
    print('Updated launcher to stock Blender, avoiding double screen processing:', launcher)
print('Backup:', backup)
