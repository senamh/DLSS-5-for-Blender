"""Compare the same saved scene with progressively added upstream components."""
import json
import os
from pathlib import Path
import shutil
import subprocess

base=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'
clean=base/'clean-comparison-34211923711'
old=base/'ready-upstream-34207206128'
root=Path(os.environ['RUNNER_TEMP'])/'scene-stack-probe'
out=Path('scene-stack-evidence').resolve()
out.mkdir()
shutil.copytree(clean,root)
profile=root/'profile'
profile.mkdir()
env=os.environ.copy()
env['BLENDER_USER_CONFIG']=str(profile)
initializer=root/'init_profile.py'
initializer.write_text("import bpy\nbpy.context.preferences.system.shader_compilation_method='SUBPROCESS'\nbpy.context.preferences.system.gpu_shader_workers=1\nbpy.context.preferences.filepaths.use_load_ui=False\nbpy.ops.wm.save_userpref()\n")
with (out/'profile.log').open('w') as log:
    subprocess.run([str(clean/'blender.exe'),'--background','--factory-startup','--disable-autoexec',
        '--python-exit-code','1','--python',str(initializer)],env=env,stdout=log,
        stderr=subprocess.STDOUT,check=True,timeout=30)
for name in ['opengl32.dll','dlss5-feed.addon64','renodx-dlss5.addon64','nvngx_dlss.dll','nvngx_dlssnr.dll']:
    shutil.copyfile(old/name,root/(name+'.disabled' if name in ['opengl32.dll','dlss5-feed.addon64','renodx-dlss5.addon64'] else name))
if os.environ.get('FEEDER_ADDON_PATH'):
    shutil.copyfile(os.environ['FEEDER_ADDON_PATH'],root/'dlss5-feed.addon64.disabled')
shutil.copytree(old/'reshade-shaders',root/'reshade-shaders')
results=[]
project=Path(r'C:\Users\User\Downloads\Apple vision pro.blend')
if not project.exists():
    project=Path(r'C:\Users\User\Downloads\Apple vision pro\Apple vision pro.blend')
assert project.exists(),'Saved scene missing'
for mode,enabled in [('full',{'opengl32.dll','dlss5-feed.addon64','renodx-dlss5.addon64'})]:
    folder=out/mode
    folder.mkdir()
    for name in ['opengl32.dll','dlss5-feed.addon64','renodx-dlss5.addon64']:
        p=root/name
        disabled=root/(name+'.disabled')
        if name in enabled and disabled.exists(): disabled.rename(p)
        elif name not in enabled and p.exists(): p.rename(disabled)
    # Fresh upstream config: no inherited host layout, old preset or debug mode.
    (root/'ReShade.ini').write_text('[ADDON]\nAddonPath=.\\\n[GENERAL]\nEffectSearchPaths=.\\reshade-shaders\\Shaders\\**\nTextureSearchPaths=.\\reshade-shaders\\Textures\\**\nPresetPath=.\\ReShadePreset.ini\nPreprocessorDefinitions=DLSS5_MV_PROVIDER=3\nSkipLoadingDisabledEffects=1\n[INPUT]\nKeyOverlay=119,0,0,0\nKeyReload=118,0,0,0\nKeyScreenshot=117,0,0,0\nInputProcessing=2\n[OVERLAY]\nTutorialProgress=4\n[SCREENSHOT]\nSavePath='+str(folder)+'\nFileNaming=present-%Count%\nFileFormat=1\nSaveOverlayShot=1\n[RenoDX.DLSS5]\nEnableHooks=2\nNeuralUplift=1\nNREnableUpscaling=0\n')
    (root/'ReShadePreset.ini').write_text('Techniques=Lumenite_Kernel@lumenite_Kernel.fx,DLSS5_Feed@DLSS5_Feed.fx\nTechniqueSorting=Lumenite_Kernel@lumenite_Kernel.fx,DLSS5_Feed@DLSS5_Feed.fx\n[DLSS5_Feed.fx]\nPreprocessorDefinitions=DLSS5_MV_PROVIDER=3\nDEBUG_VIEW=0\n')
    if mode=='reshade':
        (root/'ReShadePreset.ini').write_text('Techniques=\n')
    ini=root/'ReShade.ini'
    ini.write_text(ini.read_text().replace('[GENERAL]\n','[GENERAL]\nNoReloadOnInit=1\n'))
    (root/'dlss5-feed.cfg').write_text('enabled=1\nmode=2\n')
    for log in root.glob('*.log'): log.unlink()
    result={'mode':mode}
    try:
        with (folder/'console.log').open('w') as log:
            p=subprocess.run([str(root/'blender.exe'),'--disable-autoexec',
                '--gpu-backend','opengl','-p','0','0','1280','720','--python-exit-code','1','--python',
                str(Path(__file__).with_name('probe_scene_ui.py').resolve()),'--',str(folder)],
                cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=75)
        result['exit_code']=p.returncode
    except subprocess.TimeoutExpired: result['timeout']=True
    for log in root.glob('*.log'): shutil.copyfile(log,folder/log.name)
    logs='\n'.join(p.read_text(errors='replace') for p in folder.glob('*.log'))
    result['nr_confirmed']='inline feature 18 evaluation succeeded' in logs
    result['mismatch']='input mismatch:' in logs
    result['ui_completed']=(folder/'ui.json').exists()
    results.append(result)
    (out/'report.json').write_text(json.dumps(results,indent=2))
    if not result['ui_completed']:
        break
print(json.dumps(results,indent=2))
if os.environ.get('FEEDER_ADDON_PATH') and results and results[-1].get('nr_confirmed') and results[-1].get('ui_completed') and not results[-1].get('mismatch'):
    candidate=base/('candidate-gl-views-'+os.environ['GITHUB_RUN_ID'])
    shutil.copytree(root,candidate)
    (out/'candidate.json').write_text(json.dumps({'path':str(candidate),'launcher_created':False},indent=2))

