"""Capture upstream depth diagnostic in an isolated copy; no installation changes."""
import json, os, re, shutil, subprocess
from pathlib import Path
base=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'
root=Path(os.environ['RUNNER_TEMP'])/('depth-audit-'+os.environ['GITHUB_RUN_ID'])
out=Path('depth-evidence').resolve();out.mkdir()
shutil.copytree(base/'preview-5070-34216277728',root)
ini=root/'ReShade.ini';s=ini.read_text()
s=re.sub(r'^SavePath=.*$',lambda m:'SavePath='+str(out),s,flags=re.M);ini.write_text(s)
preset=root/'ReShadePreset.ini'
preset.write_text('Techniques=Lumenite_Kernel@lumenite_Kernel.fx,DLSS5_Feed@DLSS5_Feed.fx,DLSS5_Feed_Debug@DLSS5_Feed.fx\nTechniqueSorting=Lumenite_Kernel@lumenite_Kernel.fx,DLSS5_Feed@DLSS5_Feed.fx,DLSS5_Feed_Debug@DLSS5_Feed.fx\n[DLSS5_Feed.fx]\nPreprocessorDefinitions=DLSS5_MV_PROVIDER=3\nDEBUG_VIEW=1\n')
(root/'dlss5-feed.cfg').write_text('enabled=0\nmode=2\n')
for p in root.glob('*.log'):p.unlink()
env=os.environ.copy();env['BLENDER_USER_CONFIG']=str(root/'profile')
with (out/'console.log').open('w') as f:
    p=subprocess.run([str(root/'blender.exe'),'--disable-autoexec','--gpu-backend','opengl','-p','0','0','1280','720','--python-exit-code','1','--python',str(Path(__file__).with_name('audit_depth_ui.py').resolve()),'--',str(out)],cwd=root,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=65)
for f in root.glob('*.log'):shutil.copyfile(f,out/f.name)
(out/'process.json').write_text(json.dumps({'exit_code':p.returncode,'source_installation_changed':False}))
assert p.returncode==0 and (out/'audit.json').exists()

