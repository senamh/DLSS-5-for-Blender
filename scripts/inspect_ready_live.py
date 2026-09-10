"""Read-only snapshot of the installed upstream runtime and its settings."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import time

root=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'/'ready-upstream-34207206128'
out=Path('live-evidence')
out.mkdir()
report={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'installation':str(root),'read_only':True}
command="Get-CimInstance Win32_Process -Filter \"Name='blender.exe'\" | Select-Object ProcessId,ExecutablePath,CreationDate | ConvertTo-Json -Compress"
report['processes']=subprocess.check_output(['powershell','-NoProfile','-Command',command],text=True).strip()
report['files']={}
for name in ['ReShade.ini','ReShadePreset.ini','dlss5-feed.cfg','ReShade.log','dlss5-feed.log']:
    p=root/name
    if not p.exists():
        report['files'][name]={'missing':True}
        continue
    stat=p.stat()
    text=p.read_text(errors='replace')
    report['files'][name]={'modified_utc':datetime.datetime.fromtimestamp(stat.st_mtime,datetime.timezone.utc).isoformat(),
        'age_seconds':round(time.time()-stat.st_mtime),'size':stat.st_size}
    (out/name).write_text(text)
    if name.endswith('.log'):
        report['files'][name]['relevant_lines']=[line for line in text.splitlines() if any(s in line.lower()
            for s in ['evaluation succeeded','feature 18','config:','active settings','effects:',
                'failed','error','delivered','disabled','not installed','session ready'])][-35:]
    else:
        report['files'][name]['content']=text
(out/'report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))

