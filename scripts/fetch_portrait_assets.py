"""Download only hash-checked existing public scan assets, not runtime binaries."""
import hashlib
from pathlib import Path
import sys
import urllib.request
import urllib.error
import time

FILES = {
    'LeePerrySmith.glb': 'cff335de726fa518c1ef80f4c8aa540037b2f5b2',
    'Map-COL.jpg': '7407030a5e653d5f8080223a99713ac8c9d370a7',
    'Infinite-Level_02_Tangent_SmoothUV.jpg': 'e8a6361d798a96d335052680a98488dcfba95514',
    'LeePerrySmith_License.txt': '13a60bdc1d384093adbb838cbf1b105f888cf125',
}
root = Path(sys.argv[1])
assets = root/'assets'
assets.mkdir(parents=True, exist_ok=True)
for name, expected in FILES.items():
    urls = ['https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/LeePerrySmith/'+name,
            'https://cdn.jsdelivr.net/gh/mrdoob/three.js@dev/examples/models/gltf/LeePerrySmith/'+name,
            'https://threejs.org/examples/models/gltf/LeePerrySmith/'+name]
    if (assets/name).exists():
        data = (assets/name).read_bytes()
    else:
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urls[attempt], timeout=20) as response:
                    data = response.read(10_000_000)
                break
            except urllib.error.HTTPError as error:
                if error.code not in (429, 502, 503, 504) or attempt == 2:
                    raise
                time.sleep(2)
    actual = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
    if actual != expected:
        raise ValueError('Asset changed: '+name)
    (assets/name).write_bytes(data)
print('ASSETS_VERIFIED', root)
