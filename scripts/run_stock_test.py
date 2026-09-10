"""Acquire official portable Blender in test workspace and run stock integration test."""
import hashlib
import os
from pathlib import Path
import subprocess
import shutil
import urllib.request
import zipfile

existing = []
steam = Path('C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe')
if steam.is_file():
    version = subprocess.run([str(steam), '--version'], capture_output=True, text=True, timeout=20, check=True)
    print('Testing user-selected Steam Blender:', version.stdout.splitlines()[0], flush=True)
    subprocess.run([str(steam), '--background', '--factory-startup', '--python-exit-code', '1',
                    '--python', str(Path('scripts/test_stock_render.py').resolve())], check=True, timeout=300)
    raise SystemExit(0)
if shutil.which('blender'):
    existing.append(Path(shutil.which('blender')))
existing.extend((Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'Blender Foundation').glob('Blender */blender.exe'))
for candidate in sorted(set(existing), reverse=True):
    version = subprocess.run([str(candidate), '--version'], capture_output=True, text=True, timeout=20)
    if version.returncode == 0 and version.stdout.startswith('Blender 5.2.'):
        print('Testing installed Blender 5.2:', candidate, flush=True)
        subprocess.run([str(candidate), '--background', '--factory-startup', '--python-exit-code', '1',
                        '--python', str(Path('scripts/test_stock_render.py').resolve())], check=True, timeout=300)
        raise SystemExit(0)

root = Path(os.environ['RUNNER_TEMP']) / ('stock-blender-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'])
root.mkdir(exist_ok=False)
archive = root/'blender.zip'
urllib.request.urlretrieve('https://download.blender.org/release/Blender5.2/blender-5.2.1-windows-x64.zip', archive)
with archive.open('rb') as stream:
    if hashlib.file_digest(stream, 'sha256').hexdigest() != '0e631dad7d0cad6d5d18abdd2e2550f6c0213215334eda00ddbd3d22b96ecb2c':
        raise ValueError('Official Blender checksum mismatch')
with zipfile.ZipFile(archive) as bundle:
    bundle.extractall(root)
blender = root/'blender-5.2.1-windows-x64/blender.exe'
subprocess.run([str(blender), '--background', '--factory-startup', '--python-exit-code', '1',
                '--python', str(Path('scripts/test_stock_render.py').resolve())], check=True, timeout=300)

