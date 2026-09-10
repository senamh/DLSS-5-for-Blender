"""Verify native controls and promote only a successful isolated candidate."""
import json
import os
from pathlib import Path
import shutil
import subprocess

base=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'
source=base/'candidate-gl-views-34215539455'
root=base/('preview-5070-'+os.environ['GITHUB_RUN_ID'])
out=Path('preview-evidence').resolve()
out.mkdir()
shutil.copytree(source,root)
shutil.copyfile(Path(__file__).with_name('start_preview.py'),root/'start_preview.py')
ini=root/'ReShade.ini'
s=ini.read_text()
import re
s=re.sub(r'^SavePath=.*$',lambda m:'SavePath='+str(out),s,flags=re.M)
ini.write_text(s)
preset=root/'ReShadePreset.ini'
s=preset.read_text()
s='KeyDLSS5_Feed@DLSS5_Feed.fx=121,0,0,0\n'+s
preset.write_text(s)
for log in root.glob('*.log'): log.unlink()
env=os.environ.copy()
env['BLENDER_USER_CONFIG']=str(root/'profile')
with (out/'console.log').open('w') as log:
    p=subprocess.run([str(root/'blender.exe'),'--disable-autoexec','--gpu-backend','opengl',
        '-p','0','0','1280','720','--python-exit-code','1','--python',
        str(Path(__file__).with_name('verify_preview_ui.py').resolve()),'--',str(out)],
        env=env,cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=90)
for log in root.glob('*.log'): shutil.copyfile(log,out/log.name)
logs='\n'.join(p.read_text(errors='replace') for p in out.glob('*.log'))
ui=json.loads((out/'ui.json').read_text()) if (out/'ui.json').exists() else {}
report={'exit_code':p.returncode,'nr_confirmed':'inline feature 18 evaluation succeeded' in logs,
    'mismatch':'input mismatch:' in logs,'menu_preserves_view':any(e.get('menu_preserves_view') for e in ui.get('events',[])),
    'rotation_exercised':ui.get('view_rotation_exercised',False),'path':str(root)}
(out/'report.json').write_text(json.dumps(report,indent=2))
assert p.returncode==0 and report['nr_confirmed'] and not report['mismatch'] and report['menu_preserves_view'] and report['rotation_exercised'],report
# Leave the validated runtime and project untouched; a separate launcher opts in.
shots=root/'Screenshots'
shots.mkdir(exist_ok=True)
s=ini.read_text()
s=re.sub(r'^SavePath=.*$',lambda m:'SavePath='+str(shots),s,flags=re.M)
ini.write_text(s)
license_dir=root/'Feeder-source'
license_dir.mkdir()
for src,dst in [('patched-addon/LICENSE','LICENSE'),('patched-addon/src/dlss5-feed.cpp','dlss5-feed.cpp'),('scripts/patch_feeder_gl_views.py','patch_feeder_gl_views.py')]:
    shutil.copyfile(src,license_dir/dst)
(root/'README-preview.txt').write_text('RTX 5070 / Blender 5.2.1 Cycles viewport preview\nF8: settings (close to orbit). F10: neural feed On/Off. F7: reload after opening a file or resizing. F6: screenshot.\nN panel > DLSS 5 contains the same controls. Normal middle mouse navigation with the ReShade menu closed.\nAutomatic delayed shader loading on start. Use Rendered shading.\nReShade screen output only: F12 saved renders are not processed.\nUpstream Feeder MIT source included with guarded OpenGL view mapping fix. NVIDIA runtime and neural model unmodified.\n')
# Resolve redirected Desktop via Windows rather than assuming its location.
desktop=Path(subprocess.check_output(['powershell','-NoProfile','-Command',"[Environment]::GetFolderPath('Desktop')"],text=True).strip())
launcher=desktop/'Blender-DLSS5-5070.cmd'
launcher.write_text('@echo off\nsetlocal\nset "BLENDER_USER_CONFIG='+str(root/'profile')+'"\ncd /d "'+str(root)+'"\nstart "" "'+str(root/'blender.exe')+'" --disable-autoexec --gpu-backend opengl -p 0 0 1280 720 --python "'+str(root/'start_preview.py')+'" %*\n',encoding='utf-8')
report['launcher']=str(launcher)
(out/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))

