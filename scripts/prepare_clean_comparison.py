"""Create a separate stock OpenGL comparison launcher; never edit a project."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

source=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'/'ready-upstream-34207206128'
target=source.parent/('clean-comparison-'+os.environ['GITHUB_RUN_ID'])
injectors={'dxgi.dll','opengl32.dll','version.dll','winmm.dll','d3d11.dll','d3d12.dll',
    'dinput8.dll','d3d9.dll','dbghelp.dll','wininet.dll','nukem.dll','screenshots'}
def ignore(folder,names):
    if Path(folder)!=source:
        return []
    return [n for n in names if n.lower() in injectors or
        n.lower().startswith(('reshade','renodx','dlss5','nvngx_dlss','optiscaler','deep-fried-chicken','sl.')) or
        n.lower().endswith(('.addon','.addon32','.addon64','.log','.disabled'))]

assert source.is_dir(),'Tested Blender installation missing'
assert shutil.disk_usage(source).free>4*1024**3,'Need 4 GB free for a separate comparison copy'
excluded=ignore(str(source),[p.name for p in source.iterdir()])
shutil.copytree(source,target,ignore=ignore)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(source/'blender.exe')==sha(target/'blender.exe')
assert not any((target/name).exists() for name in injectors)
assert not list(target.glob('*.addon64'))
# The same existing startup selects Cycles/OptiX, but no injection DLLs or
# neural consumers exist in this copy. Opening a .blend remains the user's step.
desktop=subprocess.check_output(['powershell','-NoProfile','-Command',"[Environment]::GetFolderPath('Desktop')"],text=True).strip()
launcher=Path(desktop)/'Blender-CLEAN-Compare.cmd'
launcher.write_text('@echo off\r\ncd /d "'+str(target)+'"\r\nstart "" "'+str(target/'blender.exe')+'" --factory-startup --disable-autoexec --gpu-backend opengl -p 0 0 1280 720 --python "'+str(target/'start_ready.py')+'"\r\n')
report={'launcher':str(launcher),'installation':str(target),'blender_sha256':sha(target/'blender.exe'),
    'excluded_from_copy':excluded,'original_installation_changed':False,'project_files_opened_or_changed':False}
Path('clean-comparison.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))

