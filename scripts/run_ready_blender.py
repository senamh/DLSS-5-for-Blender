"""Apply the upstream OpenGL recipe to an isolated copy, never the Steam install."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

from prepare_runtime_test import digest

LUMENITE_SHA = '678f034cec0d42cb910306404925db8e5aa457b26e6d788ff2af00a8b2fa7f97'
HEADERS = {
    'ReShade.fxh':'6dabfbbaf968c3871905d2ea17f96572ff7b1cec01310b5d0e5252b66b30174f',
    'ReShadeUI.fxh':'78adf672df47460297eb9fe6dd238d2aafa24510b52b84feb1a745dff70eb901',
    'DrawText.fxh':'b79cc4dfb3e98bcf4c06193d00ea7631d74f467f73a4deeeee13e71336d3e680',
}


def main():
    root = Path(os.environ['RUNNER_TEMP'])/('ready-feeder-'+os.environ['GITHUB_RUN_ID'])
    evidence = Path('ready-blender-evidence').resolve()
    evidence.mkdir(exist_ok=False)
    original = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Blender')
    target = root/'blender'
    report = {'source_blender_modified':False,'custom_NR_code_used':False}
    try:
        if shutil.disk_usage(root).free < 5*1024**3:
            raise ValueError('Need 5 GB free for isolated Blender copy')
        # Exclude existing injectors from the TEST COPY only. They can otherwise
        # silently hook this supposedly isolated experiment as well.
        excluded = {'reshade-shaders','dxgi.dll','opengl32.dll','version.dll','winmm.dll',
            'd3d11.dll','d3d12.dll','dinput8.dll','d3d9.dll','dbghelp.dll',
            'wininet.dll','nukem.dll','dlss5-feed.cfg'}
        def ignore(folder, names):
            if Path(folder) != original:
                return []
            return [n for n in names if n.lower() in excluded or
                n.lower().startswith(('reshade','optiscaler','nvngx_dlss','renodx','dlss5-feed','deep-fried-chicken','sl.')) or
                n.lower().endswith(('.addon','.addon32','.addon64','.log'))]
        report['excluded_existing_mod_files'] = ignore(str(original), [p.name for p in original.iterdir()])
        shutil.copytree(original,target,ignore=ignore)
        report['blender_sha256'] = digest(target/'blender.exe')
        assert report['blender_sha256'] == digest(original/'blender.exe')
        for name in ['renodx-dlss5.addon64','nvngx_dlss.dll','nvngx_dlssnr.dll']:
            shutil.copyfile(root/'host'/name,target/name)
        shutil.copyfile(root/'host'/'dxgi.dll',target/'opengl32.dll')
        shutil.copyfile(root/'host'/'ReShade.ini',target/'ReShade.ini')
        shaders = target/'reshade-shaders'/'Shaders'
        textures = target/'reshade-shaders'/'Textures'
        shaders.mkdir(parents=True)
        textures.mkdir(parents=True)
        with zipfile.ZipFile(root/'feeder.zip') as bundle:
            for src,dest in [('dlss5-feed.addon64',target/'dlss5-feed.addon64'),
                ('reshade-shaders\\Shaders\\DLSS5_Feed.fx',shaders/'DLSS5_Feed.fx')]:
                entry = next(n for n in bundle.namelist() if n.replace(chr(92), '/').split('/')[-1] == dest.name)
                dest.write_bytes(bundle.read(entry))
        archive = root/'lumenite.zip'
        with urllib.request.urlopen('https://codeload.github.com/umar-afzaal/LumeniteFX/zip/refs/heads/mainline',timeout=30) as source:
            archive.write_bytes(source.read(10_000_000))
        if digest(archive) != LUMENITE_SHA:
            raise ValueError('LumeniteFX source changed')
        with zipfile.ZipFile(archive) as bundle:
            for entry in bundle.infolist():
                parts = entry.filename.split('/')
                if entry.is_dir() or len(parts)<3:
                    continue
                relative = Path(*parts[2:])
                if '..' in relative.parts:
                    raise ValueError('Invalid archive path')
                destination = None
                if parts[1]=='Shaders' and (str(relative)=='lumenite_Kernel.fx' or relative.parts[0]=='include'):
                    destination=shaders/relative
                if parts[1]=='Textures':
                    destination=textures/relative
                if destination:
                    destination.parent.mkdir(parents=True,exist_ok=True)
                    destination.write_bytes(bundle.read(entry))
        for name,sha in HEADERS.items():
            with urllib.request.urlopen('https://raw.githubusercontent.com/crosire/reshade-shaders/slim/Shaders/'+name,timeout=30) as source:
                (shaders/name).write_bytes(source.read(2_000_000))
            if digest(shaders/name)!=sha:
                raise ValueError('ReShade header changed: '+name)
        # Configuration follows the upstream installer. Only motion estimation
        # and the Feeder technique are enabled; no custom filter is supplied.
        with (target/'ReShade.ini').open('a') as ini:
            ini.write('\n[GENERAL]\nEffectSearchPaths=.\\reshade-shaders\\Shaders\\**\nTextureSearchPaths=.\\reshade-shaders\\Textures\\**\nPresetPath=.\\ReShadePreset.ini\nSkipLoadingDisabledEffects=1\n')
        (target/'ReShadePreset.ini').write_text('Techniques=Lumenite_Kernel@lumenite_Kernel.fx,DLSS5_Feed@DLSS5_Feed.fx\nTechniqueSorting=Lumenite_Kernel@lumenite_Kernel.fx,DLSS5_Feed@DLSS5_Feed.fx\n\n[DLSS5_Feed.fx]\nPreprocessorDefinitions=DLSS5_MV_PROVIDER=3\nDEBUG_VIEW=0\nMV_SCALE=1.000000\nMV_SIGN=1.000000,1.000000\n')
        script = Path(__file__).with_name('test_ready_blender_ui.py').resolve()
        with (evidence/'console.log').open('w') as log:
            process = subprocess.run([str(target/'blender.exe'),'--factory-startup','--disable-autoexec',
                '--gpu-backend','opengl','-p','0','0','1280','720','--python',str(script),'--',str(evidence)],
                cwd=target,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            report['exit_code']=process.returncode
    except Exception as error:
        report['error']=str(error)
    finally:
        crash = Path(os.environ['TEMP'])/'blender.crash.txt'
        if crash.exists():
            shutil.copyfile(crash,evidence/'blender.crash.txt')
        for path in target.glob('*'):
            if path.is_file() and path.suffix.lower() in {'.log','.ini','.cfg'}:
                shutil.copyfile(path,evidence/path.name)
        logs='\n'.join(p.read_text(errors='replace') for p in evidence.glob('*.log'))
        report['neural_evaluate_confirmed']='inline feature 18 evaluation succeeded' in logs
        report['source_frame_delivery_confirmed']=' delivered' in logs
        report['relevant_logs']=[line for line in logs.splitlines() if any(s in line.lower()
            for s in ['error','failed','feature 18','delivered','depth probe','mv probe','interop','opengl'])][-120:]
        (evidence/'report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
    # Isolate upstream hook compatibility after a failed full-stack run.
    # Rename components only in this disposable copy; never alter their code.
    if report.get('error') and (evidence/'console.log').exists():
        for mode in ['reshade_only', 'feeder_only']:
            folder=evidence/mode
            folder.mkdir()
            for name in ['dlss5-feed.addon64','renodx-dlss5.addon64']:
                active=target/name
                disabled=target/(name+'.disabled')
                enable=mode=='feeder_only' and name=='dlss5-feed.addon64'
                if enable and disabled.exists():
                    disabled.rename(active)
                elif not enable and active.exists():
                    active.rename(disabled)
            (target/'ReShade.ini').write_text('[ADDON]\nAddonPath=.\\\n\n[GENERAL]\nEffectSearchPaths=.\\reshade-shaders\\Shaders\\**\nTextureSearchPaths=.\\reshade-shaders\\Textures\\**\nPresetPath=.\\ReShadePreset.ini\nSkipLoadingDisabledEffects=1\n')
            for path in target.glob('*.log'):
                path.unlink()
            result={}
            try:
                with (folder/'console.log').open('w') as log:
                    run=subprocess.run([str(target/'blender.exe'),'--factory-startup','--disable-autoexec',
                        '--gpu-backend','opengl','-p','0','0','1280','720','--python',str(script),'--',str(folder)],
                        cwd=target,stdout=log,stderr=subprocess.STDOUT,timeout=75)
                    result['exit_code']=run.returncode
            except subprocess.TimeoutExpired:
                result['timed_out']=True
            for path in target.glob('*.log'):
                shutil.copyfile(path,folder/path.name)
            if crash.exists():
                shutil.copyfile(crash,folder/'blender.crash.txt')
            result['ui_completed']=(folder/'blender.json').exists()
            (folder/'result.json').write_text(json.dumps(result,indent=2))


if __name__=='__main__':
    main()

