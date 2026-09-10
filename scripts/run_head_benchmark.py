"""Render an attributed portrait and compare known NR modes without installing."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import urllib.request

from prepare_runtime_test import main as prepare_runtime

FILES = {
    'LeePerrySmith.glb': 'cff335de726fa518c1ef80f4c8aa540037b2f5b2',
    'Map-COL.jpg': '7407030a5e653d5f8080223a99713ac8c9d370a7',
    'Infinite-Level_02_Tangent_SmoothUV.jpg': 'e8a6361d798a96d335052680a98488dcfba95514',
    'LeePerrySmith_License.txt': '13a60bdc1d384093adbb838cbf1b105f888cf125',
}


def main():
    root = Path('head-benchmark').resolve()
    (root/'assets').mkdir(parents=True,exist_ok=False)
    for name, expected in FILES.items():
        url = 'https://raw.githubusercontent.com/mrdoob/three.js/dev/examples/models/gltf/LeePerrySmith/'+name
        with urllib.request.urlopen(url, timeout=30) as response:
            data = response.read(10_000_000)
        sha = hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        if sha != expected:
            raise ValueError('Asset version changed: '+name)
        (root/'assets'/name).write_bytes(data)
    (root/'ATTRIBUTION.txt').write_text('Infinite, 3D Head Scan by Lee Perry-Smith. CC BY 3.0. Based on www.triplegangers.com.\nSource: https://github.com/mrdoob/three.js/tree/dev/examples/models/gltf/LeePerrySmith\nRendered and processed for this experiment; original license is in assets/.\n')
    prepare_runtime()
    workspace = Path(os.environ['RUNNER_TEMP'])/('dlss5-'+os.environ['GITHUB_RUN_ID']+'-'+os.environ['GITHUB_RUN_ATTEMPT'])
    blender = r'C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe'
    scripts = Path(__file__).resolve().parent
    def run(script, argument, log, timeout):
        with log.open('w') as output:
            return subprocess.run([blender,'--background','--factory-startup','--disable-autoexec',
                '--python-exit-code','1','--python',str(scripts/script),'--',str(argument)],
                stdout=output,stderr=subprocess.STDOUT,timeout=timeout).returncode
    if run('render_head_benchmark.py',root,root/'render.log',240):
        raise RuntimeError('Portrait render failed; inspect render.log')
    results = []
    for style, intensity, automask in [(0,0.,0),(0,.5,0),(0,1.,0),(1,1.,0),(0,1.,1),(1,1.,1)]:
        key = f'style{style}-intensity{intensity:g}-mask{automask}'
        job = dict(input=str(root/'input.npy'),output=str(root/(key+'.npy')),
            report=str(root/(key+'.json')),bridge=str(workspace/'dlss5nr_bridge.dll'),
            runtime=str(workspace/'runtime'),style=style,intensity=intensity,automask=automask,skin=1. if automask else -1.)
        path = workspace/(key+'.json')
        path.write_text(json.dumps(job))
        code = run('nr_matrix_worker.py',path,root/(key+'.log'),120)
        result = dict(case=key,exit_code=code)
        if Path(job['report']).exists():
            result.update(json.loads(Path(job['report']).read_text()))
        results.append(result)
        (root/'report.json').write_text(json.dumps(results,indent=2))


if __name__ == '__main__':
    main()

