"""Launch only a factory test window with disposable ReShade UI settings."""
import importlib.util
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import runpy

root = Path(__file__).resolve().parents[1]
runtime = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('style_config', root / 'addon/cycles_dlss5/style_config.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)
folder = Path(tempfile.mkdtemp(prefix='dlss5-buttons-test-'))
config.prepare_profile(runtime, folder, dict(zip(config.FIELDS, config.PRESETS['BALANCED'])))
migrate = runpy.run_path(str(root / 'addon/cycles_dlss5/preview_controls.py'))['migrate_bindings']
config_text, preset_text = migrate((folder / 'ReShade.ini').read_text(), (folder / 'ReShadePreset.ini').read_text())
(folder / 'ReShade.ini').write_text(config_text)
(folder / 'ReShadePreset.ini').write_text(preset_text)
env = os.environ.copy()
env['RESHADE_BASE_PATH_OVERRIDE'] = str(folder)
env['BLENDER_USER_CONFIG'] = str(folder / 'profile')
print('BUTTON_TEST_EVIDENCE', folder, flush=True)
with (folder / 'blender.log').open('w') as log:
    process = subprocess.Popen([str(runtime / 'blender.exe'), '--factory-startup', '--disable-autoexec',
        '--gpu-backend', 'opengl', '-p', '0', '0', '1280', '720', '--python',
        str(root / 'scripts/smoke_buttons_gui.py'), '--', str(folder)], env=env, cwd=runtime,
        stdout=log, stderr=subprocess.STDOUT)
    try:
        code = process.wait(timeout=150)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
        raise
print((folder / 'blender.log').read_text(errors='replace'), flush=True)
raise SystemExit(code)
