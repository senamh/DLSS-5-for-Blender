"""Controlled hook isolation; all mutations stay inside a disposable copy."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

root=Path(os.environ['RUNNER_TEMP'])/'hook-isolation'
source=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'/'ready-upstream-34205910366'
shutil.copytree(source,root)
evidence=Path('hook-evidence').resolve()
evidence.mkdir()
script=Path(__file__).with_name('test_ready_blender_ui.py').resolve()
results=[]
for mode in ['stock','reshade_only','feeder_only']:
    enabled={'stock':set(),'reshade_only':{'opengl32.dll'},
        'feeder_only':{'opengl32.dll','dlss5-feed.addon64'}}[mode]
    for name in ['opengl32.dll','dlss5-feed.addon64','renodx-dlss5.addon64']:
        active=root/name
        disabled=root/(name+'.disabled')
        if name in enabled and disabled.exists():
            disabled.rename(active)
        elif name not in enabled and active.exists():
            active.rename(disabled)
    (root/'ReShade.ini').write_text('[ADDON]\nAddonPath=.\\\n\n[GENERAL]\nEffectSearchPaths=.\\reshade-shaders\\Shaders\\**\nTextureSearchPaths=.\\reshade-shaders\\Textures\\**\nPresetPath=.\\ReShadePreset.ini\nSkipLoadingDisabledEffects=1\n')
    for log in root.glob('*.log'):
        log.unlink()
    output=evidence/mode
    output.mkdir()
    record={'mode':mode}
    started=time.time()
    try:
        with (output/'console.log').open('w') as log:
            run=subprocess.run([str(root/'blender.exe'),'--factory-startup','--disable-autoexec',
                '--gpu-backend','opengl','-p','0','0','1280','720','--python',str(script),'--',str(output)],
                cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=75)
            record['exit_code']=run.returncode
    except subprocess.TimeoutExpired:
        record['timed_out']=True
    for log in root.glob('*.log'):
        shutil.copyfile(log,output/log.name)
    crash=Path(os.environ['TEMP'])/'blender.crash.txt'
    if crash.exists() and crash.stat().st_mtime>=started:
        shutil.copyfile(crash,output/'blender.crash.txt')
    record['ui_completed']=(output/'blender.json').exists()
    results.append(record)
    (evidence/'report.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))

