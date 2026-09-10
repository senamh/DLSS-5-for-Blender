"""Launch only a disposable Steam Blender window; verify report even on clean exit."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
output = root/'gpu-results'
output.mkdir(exist_ok=True)
with (output/'stock-ui.log').open('w', encoding='utf-8') as log:
    subprocess.run(['C:/Program Files (x86)/Steam/steamapps/common/Blender/blender.exe',
                    '--factory-startup', '--python-exit-code', '1',
                    '--python', str(root/'scripts/test_stock_ui.py')],
                   stdout=log, stderr=subprocess.STDOUT, timeout=240, check=True)
report = json.loads((output/'stock-ui/report.json').read_text(encoding='utf-8'))
print(json.dumps(report, indent=2))
if report.get('passed') is not True:
    raise SystemExit(1)

