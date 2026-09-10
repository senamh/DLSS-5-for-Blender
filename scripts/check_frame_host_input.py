"""Exercise compiled file adapter only; no GPU or NGX initialization."""
import json,subprocess,sys,tempfile,shutil
from pathlib import Path
exe=Path(sys.argv[1]).resolve();payload=Path(sys.argv[2]).resolve()
meta=json.loads((payload/'payload.json').read_text());w,h=meta['size']
cmd=[str(exe),'--validate-frame',str(w),str(h)]
valid=subprocess.run(cmd+[str(payload)],capture_output=True,text=True)
with tempfile.TemporaryDirectory() as temporary:
    bad=Path(temporary)/'bad';shutil.copytree(payload,bad)
    (bad/'depth.f32').write_bytes(b'\0')
    invalid=subprocess.run(cmd+[str(bad)],capture_output=True,text=True)
report={'input_accepted':valid.returncode==0,'truncated_depth_rejected':invalid.returncode!=0,
        'valid_exit':valid.returncode,'invalid_exit':invalid.returncode,'gpu_evaluated':False,
        'valid_log':valid.stdout,'invalid_log':invalid.stdout}
Path('frame-host-validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
assert report['input_accepted'] and report['truncated_depth_rejected']

