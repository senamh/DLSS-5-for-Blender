"""Run the unmodified upstream Feeder host with the reference RenoDX payload."""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request
import zipfile

from prepare_runtime_test import digest
from run_nr_matrix import download_video, VIDEO_ARCHIVE_SHA

FEEDER_URL = 'https://github.com/jlrouzies-fr/DLSS5-Feeder/releases/download/v0.14.0-beta.5/DLSS5-Feeder-0.14.0-beta.5.zip'
FEEDER_SHA = '5f641b1b625ba0fdd23a8e3b16b5d6b173d7bdc34b4405fd8992b78fb1482ab0'


def main():
    root = Path(os.environ['RUNNER_TEMP'])/('ready-feeder-'+os.environ['GITHUB_RUN_ID'])
    root.mkdir(exist_ok=False)
    evidence = Path('ready-feeder-evidence')
    evidence.mkdir(exist_ok=False)
    host = root/'host'
    host.mkdir()
    report = {'source': FEEDER_URL, 'custom_bridge_used': False, 'custom_color_processing': False}
    try:
        video = root/'video.zip'
        download_video(video)
        if digest(video) != VIDEO_ARCHIVE_SHA:
            raise ValueError('Reference archive checksum mismatch')
        feeder = root/'feeder.zip'
        with urllib.request.urlopen(FEEDER_URL,timeout=60) as source, feeder.open('xb') as target:
            shutil.copyfileobj(source,target)
        if digest(feeder) != FEEDER_SHA:
            raise ValueError('Upstream Feeder archive checksum mismatch')
        with zipfile.ZipFile(feeder) as bundle:
            entry = next(n for n in bundle.namelist() if n.replace('\\','/').endswith('host64/dlss5-feed-host64.exe'))
            (host/'dlss5-feed-host64.exe').write_bytes(bundle.read(entry))
        with zipfile.ZipFile(video) as bundle:
            for name in ['nvngx_dlssnr.dll','nvngx_dlss.dll','renodx-dlss5.addon64']:
                matches = [n for n in bundle.namelist() if n.replace('\\','/').split('/')[-1] == name]
                if len(matches) != 1:
                    raise ValueError('Ambiguous reference component '+name)
                (host/name).write_bytes(bundle.read(matches[0]))
            setup = next(n for n in bundle.namelist() if n.endswith('ReShade_Setup_6.8.0_Addon.exe'))
            with zipfile.ZipFile(io.BytesIO(bundle.read(setup))) as reshade:
                (host/'dxgi.dll').write_bytes(reshade.read('ReShade64.dll'))
        # Use documented startup loading, not any replacement shader or color code.
        (host/'ReShade.ini').write_text('[ADDON]\nAddonPath=.\\\nLoadFromDllMain=renodx-dlss5.addon64\n[OVERLAY]\nTutorialProgress=4\n')
        report['components'] = {p.name:digest(p) for p in host.iterdir() if p.suffix in {'.dll','.exe','.addon64'}}
        with (evidence/'console.log').open('w') as log:
            try:
                result = subprocess.run([str(host/'dlss5-feed-host64.exe'),'--test'],cwd=host,
                    stdout=log,stderr=subprocess.STDOUT,timeout=120)
                report['exit_code'] = result.returncode
            except subprocess.TimeoutExpired:
                report['error'] = 'Upstream host exceeded 120 seconds and was terminated'
    except Exception as error:
        report['error'] = str(error)
    finally:
        for path in host.rglob('*'):
            if path.is_file() and path.suffix.lower() in {'.log','.ini','.cfg'}:
                destination = evidence/path.relative_to(host)
                destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,destination)
        logs = '\n'.join(p.read_text(errors='replace') for p in evidence.rglob('*.log'))
        report['upstream_evaluations_passed'] = '--test finished: 300/300 evaluates succeeded' in logs
        report['neural_evidence_lines'] = [line for line in logs.splitlines()
            if any(s in line.lower() for s in ['feature 18','neural','dlssnr','failed','error','standby'])][-150:]
        report['limitation'] = 'Upstream host compatibility test only; not a Blender integration or visual-quality test.'
        (evidence/'report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()

