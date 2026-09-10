"""Restore the tested installation's startup state after the OFF comparison."""
import json
import os
from pathlib import Path

root=Path(os.environ['LOCALAPPDATA'])/'DLSS-Blender'/'ready-upstream-34207206128'
assert (root/'blender.exe').is_file(), 'Tested Blender copy missing'
cfg=root/'dlss5-feed.cfg'
lines=cfg.read_text().splitlines()
assert any(line.startswith('enabled=') for line in lines)
cfg.write_text('\n'.join('enabled=1' if line.startswith('enabled=') else line for line in lines)+'\n')
assert 'enabled=1' in cfg.read_text().splitlines()
(root/'READ-ME.txt').write_text('Experimental DLSS5 / stock Blender / RTX5070\nStart Blender-DLSS5-Ready-TEST.cmd on your desktop.\nHome: ReShade > Add-ons > DLSS5 Feeder > Enabled.\nF6: ReShade screenshot in this folder/screenshots.\nWhole-window effect, including UI. F12 exports do not contain it.\nUse the overlay checkbox, not live edits of dlss5-feed.cfg, to toggle.\n')
Path('finalized.json').write_text(json.dumps({'installation':str(root),'startup_enabled':True,
    'validated_run':34207206128,'new_gpu_test_started':False},indent=2))
print(Path('finalized.json').read_text())

