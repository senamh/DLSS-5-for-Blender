"""Compare pinned runtimes on the same real captured Cycles frame; no install."""
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.parse
import urllib.request
import zipfile

from prepare_runtime_test import digest, main as prepare_current

VIDEO_ARCHIVE_SHA = 'ada812f283ac75d4b0ee88cfabd7e763e5cad98424105a99acf9bd256fe387f8'
VIDEO_DLL_SHA = '4b8d19bc3eff58a084f5eca7489c921501c203450169fb82ff4f649a4482ba05'


class DownloadForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.action = attrs.get('action')
        if tag == 'input' and attrs.get('type') == 'hidden' and attrs.get('name'):
            self.fields[attrs['name']] = attrs.get('value', '')


def download_video(destination):
    url = 'https://drive.google.com/uc?export=download&id=1AB_4u3_FxvUtTZdSPSAmcDrFd2GzN_c0'
    with urllib.request.urlopen(url, timeout=60) as response:
        if 'text/html' in response.headers.get('Content-Type', ''):
            form = DownloadForm()
            form.feed(response.read(2_000_000).decode('utf-8'))
            action = urllib.parse.urlparse(form.action or '')
            if action.scheme != 'https' or action.hostname != 'drive.usercontent.google.com':
                raise ValueError('Unexpected Drive download form')
            url = form.action + '?' + urllib.parse.urlencode(form.fields)
        else:
            with destination.open('xb') as target:
                shutil.copyfileobj(response, target)
            return
    with urllib.request.urlopen(url, timeout=60) as source, destination.open('xb') as target:
        shutil.copyfileobj(source, target)


def main():
    output = Path('nr-matrix-results').resolve()
    output.mkdir(exist_ok=False)
    prepare_current()
    workspace = Path(os.environ['RUNNER_TEMP']) / ('dlss5-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT'])
    frame = Path('scene-evidence/stock-ui/raw-frames/input-1.npy').resolve(strict=True)
    shutil.copyfile(frame, output/'input.npy')
    report = dict(input_sha256=digest(frame), source_run=34201377466,
        bridge_sha256=digest(workspace/'dlss5nr_bridge.dll'), cases=[],
        limitation='Tests runtime and style through our bridge, not the complete RenoDX integration or temporal quality.')
    runtimes = {'current': workspace/'runtime'}
    try:
        archive = workspace/'video.zip'
        download_video(archive)
        if digest(archive) != VIDEO_ARCHIVE_SHA:
            raise ValueError('Video archive hash mismatch; refusing to execute')
        video = workspace/'video-runtime'
        shutil.copytree(workspace/'runtime', video)
        with zipfile.ZipFile(archive) as bundle:
            entries = [x for x in bundle.infolist() if x.filename.replace('\\', '/').split('/')[-1].lower() == 'nvngx_dlssnr.dll']
            if len(entries) != 1 or entries[0].file_size != 165840496:
                raise ValueError('Unexpected video DLL contents')
            with bundle.open(entries[0]) as source, (video/'nvngx_dlssnr.dll').open('wb') as target:
                shutil.copyfileobj(source, target)
        if digest(video/'nvngx_dlssnr.dll') != VIDEO_DLL_SHA:
            raise ValueError('Video DLL hash mismatch; refusing to execute')
        runtimes['video'] = video
    except Exception as error:
        report['video_preparation_error'] = str(error)
    blender = Path(r'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe')
    for name, runtime in runtimes.items():
        for style, intensity in [(0, 1.0), (1, 1.0), (0, 0.0)]:
            key = f'{name}-style{style}-intensity{intensity:g}'
            job = dict(input=str(frame), output=str(output/(key+'.npy')),
                report=str(output/(key+'.json')), bridge=str(workspace/'dlss5nr_bridge.dll'),
                runtime=str(runtime), style=style, intensity=intensity)
            job_path = workspace/(key+'.json')
            job_path.write_text(json.dumps(job))
            entry = dict(case=key, runtime_sha256=digest(runtime/'nvngx_dlssnr.dll'), style=style, intensity=intensity)
            with (output/(key+'.log')).open('w') as log:
                try:
                    result = subprocess.run([str(blender), '--background', '--factory-startup',
                        '--python-exit-code', '1', '--python', str(Path(__file__).with_name('nr_matrix_worker.py')),
                        '--', str(job_path)], stdout=log, stderr=subprocess.STDOUT, timeout=120)
                    entry['exit_code'] = result.returncode
                except subprocess.TimeoutExpired:
                    entry['error'] = 'Timed out; isolated worker terminated'
            if Path(job['report']).exists():
                entry.update(json.loads(Path(job['report']).read_text()))
            report['cases'].append(entry)
            (output/'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

