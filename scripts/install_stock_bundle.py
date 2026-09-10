"""Prepare a versioned local bundle from verified job files, with a launch command."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

repo = Path(__file__).resolve().parents[1]
key = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
tested = Path(os.environ['RUNNER_TEMP'])/('dlss5-'+key)
destination = Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'/key
destination.mkdir(parents=True, exist_ok=False)
shutil.copytree(repo/'addon/cycles_dlss5', destination/'addon/cycles_dlss5',
                ignore=shutil.ignore_patterns('__pycache__'))
shutil.copytree(tested/'runtime', destination/'runtime')
shutil.copyfile(tested/'dlss5nr_bridge.dll', destination/'dlss5nr_bridge.dll')
shutil.copyfile(repo/'scripts/start_stock.py', destination/'start_stock.py')
for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
    shutil.copyfile(repo/name, destination/name)
subprocess.run([sys.executable, str(destination/'addon/cycles_dlss5/probe.py'),
                '--runtime', str(destination/'runtime'), '--bridge', str(destination/'dlss5nr_bridge.dll'),
                '--output', str(destination/'validation'), '--order', 'RGB', '--trust-runtime'],
               check=True, timeout=150)
blender = 'C:\\Program Files (x86)\\Steam\\steamapps\\common\\Blender\\blender.exe'
command = '@echo off\n"'+blender+'" --python-exit-code 1 --python "%~dp0start_stock.py" %*\n'
(destination/'Start-DLSS-Blender.cmd').write_text(command, encoding='utf-8')
desktop_buffer = ctypes.create_unicode_buffer(32768)
desktop_result = ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, desktop_buffer)
shortcut = None
if desktop_result == 0:
    shortcut = Path(desktop_buffer.value)/('DLSS-Blender-'+key+'.cmd')
    with shortcut.open('x', encoding='utf-8') as stream:
        stream.write('@echo off\ncall "'+str(destination/'Start-DLSS-Blender.cmd')+'" %*\n')
report = dict(folder=str(destination), launcher=str(destination/'Start-DLSS-Blender.cmd'), desktop=str(shortcut))
(repo/'gpu-results/install.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))

