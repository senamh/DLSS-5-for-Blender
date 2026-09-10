"""Restore the upstream motion provider and expose ReShade's native reload key."""
import configparser
import json
import io
import os
from pathlib import Path
import shutil
import subprocess

installed=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'/'ready-upstream-34207206128'
root=Path(os.environ['RUNNER_TEMP'])/'ready-buffer-repair'
out=Path('buffer-evidence').resolve()
out.mkdir()
shutil.copytree(installed,root)
def configure(folder):
    for filename,section in [('ReShade.ini','GENERAL'),('ReShadePreset.ini','DLSS5_Feed.fx')]:
        ini=configparser.RawConfigParser(strict=False)
        ini.optionxform=str
        text=(folder/filename).read_text()
        preset=filename=='ReShadePreset.ini'
        ini.read_string(('[__PRESET_ROOT__]\n' if preset else '')+text)
        if section not in ini:
            ini[section]={}
        definitions=[s for s in ini[section].get('PreprocessorDefinitions','').split(',')
            if s and not s.startswith('DLSS5_MV_PROVIDER=')]
        ini[section]['PreprocessorDefinitions']=','.join(definitions+['DLSS5_MV_PROVIDER=3'])
        if filename=='ReShade.ini':
            ini['INPUT']['KeyReload']='118,0,0,0'
        output=io.StringIO()
        ini.write(output,space_around_delimiters=False)
        text=output.getvalue()
        if preset:
            text=text.removeprefix('[__PRESET_ROOT__]\n')
        (folder/filename).write_text(text)

configure(root)
for log in root.glob('*.log'):
    log.unlink()
script=Path(__file__).with_name('test_ready_blender_ui.py').resolve()
with (out/'console.log').open('w') as log:
    run=subprocess.run([str(root/'blender.exe'),'--factory-startup','--disable-autoexec',
        '--gpu-backend','opengl','-p','0','0','1280','720','--python',str(script),'--',str(out)],
        cwd=root,stdout=log,stderr=subprocess.STDOUT,timeout=90)
for log in root.glob('*.log'):
    shutil.copyfile(log,out/log.name)
nr=(root/'ReShade.log').read_text(errors='replace')
feed=(root/'dlss5-feed.log').read_text(errors='replace')
report={'exit_code':run.returncode,'nr_confirmed':'inline feature 18 evaluation succeeded' in nr,
    'motion_provider_confirmed':'DLSS5_MV_PROVIDER=3 (LumeniteFX Kernel) -> Lumenite_Kernel (enabled)' in feed,
    'buffer_mismatch':'input mismatch:' in feed,'reload_after_resize_requires_user_F7':True}
if run.returncode==0 and report['nr_confirmed'] and report['motion_provider_confirmed'] and not report['buffer_mismatch']:
    # Back up only the two configs this repair changes.
    for filename in ['ReShade.ini','ReShadePreset.ini']:
        shutil.copyfile(installed/filename,installed/(filename+'.before-buffer-repair-'+os.environ['GITHUB_RUN_ID']))
    configure(installed)
    desktop=subprocess.check_output(['powershell','-NoProfile','-Command',"[Environment]::GetFolderPath('Desktop')"],text=True).strip()
    launcher=Path(desktop)/'Blender-DLSS5-Ready-TEST.cmd'
    launcher.write_text('@echo off\r\ncd /d "'+str(installed)+'"\r\nstart "" "'+str(installed/'blender.exe')+'" --factory-startup --disable-autoexec --gpu-backend opengl -p 0 0 1280 720 --python "'+str(installed/'start_ready.py')+'"\r\n')
    report['installed']=True
(out/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
if not report.get('installed'):
    raise SystemExit(1)

