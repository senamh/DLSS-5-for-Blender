"""Fetch two explicitly attributed official Blender demo files, not third-party code."""
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.request import urlopen, Request

root = Path(tempfile.mkdtemp(prefix='dlss5-official-demos-'))
demos = [
    dict(file='blender-3.5-splash.blend', title='Cozy Kitchen', author='Nicole Morena', license='CC-BY-SA',
         url='https://download.blender.org/demo/splash/blender-3.5-splash.blend'),
    dict(file='blender-5.2-splash.blend', title='Panthera Spelaea', author='Joanna Kobierska; see bundled README for full credits', license='CC-BY',
         url='https://download.blender.org/demo/splash/blender-5.2-splash.blend'),
]
print('OFFICIAL_DEMOS', root, flush=True)
for demo in demos:
    path = root / demo['file']
    request = Request(demo['url'], headers={'User-Agent': 'Mozilla/5.0 (Blender addon validation)'})
    with urlopen(request, timeout=60) as response, path.open('xb') as output:
        if not response.url.startswith('https://download.blender.org/'):
            raise ValueError('Unexpected download host')
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    demo['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    demo['bytes'] = path.stat().st_size
    print('DOWNLOADED', demo['title'], demo['bytes'], flush=True)
(root / 'SOURCES.json').write_text(json.dumps({'catalog': 'https://www.blender.org/download/demo-files/',
    'demos': demos, 'note': 'Do not enable embedded scripts. Originals are read-only test inputs.'}, indent=2))
