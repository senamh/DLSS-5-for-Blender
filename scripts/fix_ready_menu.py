"""Validate the new startup in a copy, then update only the installed Python startup."""
import configparser
import json
import os
from pathlib import Path
import shutil
import subprocess

installed=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'/'ready-upstream-34207206128'
root=Path(os.environ['RUNNER_TEMP'])/'ready-menu-test'
out=Path('menu-evidence').resolve()
out.mkdir()
report={}
try:
    shutil.copytree(installed,root)
    for log in root.glob('*.log'):
        log.unlink()
    ini=configparser.RawConfigParser(strict=False)
    ini.optionxform=str
    ini.read(root/'ReShade.ini')
    ini['SCREENSHOT']['SavePath']=str(out)
    ini['SCREENSHOT']['FileNaming']='menu-%Count%'
    ini['SCREENSHOT']['SaveOverlayShot']='1'
    with (root/'ReShade.ini').open('w') as f:
        ini.write(f,space_around_delimiters=False)
    script=Path(__file__).with_name('test_ready_menu.py').resolve()
    with (out/'console.log').open('w') as log:
        result=subprocess.run([str(root/'blender.exe'),'--factory-startup','--disable-autoexec',
            '--gpu-backend','opengl','-p','0','0','1280','720','--python',str(script),'--',str(out)],
            cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=75)
    report['exit_code']=result.returncode
    ui=json.loads((out/'ui.json').read_text())
    report.update(ui)
    if result.returncode or ui['redraws']<100:
        raise RuntimeError('Startup redraw loop did not pass')
    startup=Path(__file__).with_name('start_ready.py')
    # Existing Blender processes and their open projects are untouched.
    shutil.copyfile(startup,installed/'start_ready.py')
    report['startup_updated']=str(installed/'start_ready.py')
    report['restart_required']=True
except Exception as error:
    report['error']=str(error)
finally:
    for log in root.glob('*.log'):
        shutil.copyfile(log,out/log.name)
    (out/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if report.get('error'):
    raise SystemExit(1)

