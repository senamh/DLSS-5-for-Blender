"""Repeat the successful stock stack on a portrait, then expose a separate test launcher."""
import configparser
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.request
from run_head_benchmark import FILES

def main():
    source=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'/'ready-upstream-34205910366'
    root=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'/('ready-upstream-'+os.environ['GITHUB_RUN_ID'])
    evidence=Path('ready-ab-evidence').resolve()
    evidence.mkdir()
    report={'custom_image_processing':False,'source_run':34205910366}
    try:
        if not source.is_dir():
            raise RuntimeError('Verified test copy no longer exists')
        expected={
            'blender.exe':'8f7a131ad8bc148edc218b334f07d92a57f5a357fa66d913b290537fd8353c06',
            'opengl32.dll':'0cee63f9c9f13f3ac909c5b4903f4dbb4b719a7ab3b4f13b0deaf83c814b94f7',
            'renodx-dlss5.addon64':'a8b5e164cbc3222a5d62bbddf44a2cc68d359b0caf729e55f2877c49e73e9aac',
            'nvngx_dlssnr.dll':'4b8d19bc3eff58a084f5eca7489c921501c203450169fb82ff4f649a4482ba05',
            'nvngx_dlss.dll':'c85f971ce023c9f3492fc7455f0b01a24ba18ea39636407a846902c4360b0b7e',
        }
        for name,sha in expected.items():
            if hashlib.sha256((source/name).read_bytes()).hexdigest()!=sha:
                raise RuntimeError('Verified component changed: '+name)
        shutil.copytree(source,root)
        for log in root.glob('*.log'):
            log.unlink()
        assets=evidence/'assets'
        assets.mkdir()
        for name,sha in FILES.items():
            for attempt in range(3):
                try:
                    with urllib.request.urlopen('https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/LeePerrySmith/'+name,timeout=30) as response:
                        data=response.read(10_000_000)
                    break
                except OSError:
                    if attempt==2:
                        raise
                    time.sleep(2)
            actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            if actual!=sha:
                raise ValueError('Upstream asset changed: '+name)
            (assets/name).write_bytes(data)
        (evidence/'ATTRIBUTION.txt').write_text('Lee Perry-Smith / Infinite, CC BY 3.0. Source: https://github.com/mrdoob/three.js/tree/dev/examples/models/gltf/LeePerrySmith\n')
        ini=configparser.RawConfigParser(strict=False)
        ini.optionxform=str
        ini.read(root/'ReShade.ini')
        # The D3D12 test host's forced early load is not part of the upstream
        # OpenGL installer recipe. Let ReShade load the consumer normally.
        ini['ADDON'].pop('LoadFromDllMain',None)
        # Print Screen can open Windows Snipping Tool and steal focus.
        # F6 is a dedicated ReShade capture shortcut in this test copy.
        ini['INPUT']['KeyScreenshot']='117,0,0,0'
        ini['SCREENSHOT']['SavePath']=str(evidence)
        ini['SCREENSHOT']['FileNaming']='ready-%Count%'
        ini['SCREENSHOT']['SaveBeforeShot']='0'
        with (root/'ReShade.ini').open('w') as output:
            ini.write(output,space_around_delimiters=False)
        script=Path(__file__).with_name('test_ready_ab.py').resolve()
        with (evidence/'console.log').open('w') as log:
            result=subprocess.run([str(root/'blender.exe'),'--factory-startup','--disable-autoexec',
                '--gpu-backend','opengl','-p','0','0','1280','720','--python',str(script),'--',str(evidence)],
                cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=110)
        report['exit_code']=result.returncode
        logs=(root/'ReShade.log').read_text(errors='replace')
        feed=(root/'dlss5-feed.log').read_text(errors='replace')
        report['neural_evaluate_confirmed']='inline feature 18 evaluation succeeded' in logs
        report['source_frame_delivery_confirmed']=' delivered' in feed
        report['screenshots']=[p.name for p in evidence.glob('*.png')]
        if result.returncode or not report['neural_evaluate_confirmed'] or not (evidence/'ab.json').exists():
            raise RuntimeError('Repeat test failed; launcher withheld')
        cfg=root/'dlss5-feed.cfg'
        cfg.write_text('\n'.join('enabled=1' if line.startswith('enabled=') else line
            for line in cfg.read_text().splitlines())+'\n')
        # The old snapshot addon is not loaded: this launcher is a distinct,
        # factory-startup stock Blender with untouched upstream GPU components.
        shutil.copyfile(Path(__file__).with_name('start_ready.py'),root/'start_ready.py')
        ini.read(root/'ReShade.ini')
        ini['SCREENSHOT']['SavePath']=str(root/'screenshots')
        (root/'screenshots').mkdir(exist_ok=True)
        with (root/'ReShade.ini').open('w') as output:
            ini.write(output,space_around_delimiters=False)
        desktop=subprocess.check_output(['powershell','-NoProfile','-Command',"[Environment]::GetFolderPath('Desktop')"],text=True).strip()
        launcher=Path(desktop)/'Blender-DLSS5-Ready-TEST.cmd'
        launcher.write_text('@echo off\r\ncd /d "'+str(root)+'"\r\nstart "" "'+str(root/'blender.exe')+'" --factory-startup --disable-autoexec --gpu-backend opengl --python "'+str(root/'start_ready.py')+'"\r\n')
        report['launcher']=str(launcher)
        report['installation']=str(root)
    except Exception as error:
        report['error']=str(error)
    finally:
        for log in root.glob('*.log'):
            shutil.copyfile(log,evidence/log.name)
        (evidence/'report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))
    if report.get('error'):
        raise SystemExit(1)

if __name__=='__main__':
    main()

