"""Download a pinned candidate; never load DLLs or alter installed software."""
import hashlib
import os
from pathlib import Path
import shutil
import urllib.request
import zipfile

URL = 'https://github.com/RankFTW/rhi-repo/releases/download/dlssnr-310.8.SF-v2/nvngx_dlssnr_310.8.SF-v2.zip'
ARCHIVE_SHA = '1da35941894994eb087e017577829e492454e9bae3a6a9397027069ceb74955c'
DLL_SHA = '6eb209e764f39872625debd6abaf45e2bb6322f6f270f781f70c059ae30b3927'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    root = Path(os.environ['RUNNER_TEMP']) / (
        'dlss5-' + os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT'])
    root.mkdir(exist_ok=False)
    runtime = root / 'runtime'
    (runtime / 'caller').mkdir(parents=True)
    for name, destination in (
        ('dlss5nr_bridge.dll', root / 'dlss5nr_bridge.dll'),
        ('nvngx.dll_blender.dll', runtime / 'caller' / 'nvngx.dll_blender.dll'),
    ):
        matches = list(Path('gpu-components').rglob(name))
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one compiled {name}')
        shutil.copyfile(matches[0], destination)
    archive = root / 'candidate.zip'
    with urllib.request.urlopen(URL, timeout=60) as response, archive.open('xb') as stream:
        shutil.copyfileobj(response, stream)
    if digest(archive) != ARCHIVE_SHA:
        raise ValueError('Runtime archive checksum mismatch')
    destination = runtime / 'nvngx_dlssnr.dll'
    with zipfile.ZipFile(archive) as bundle:
        entries = [x for x in bundle.infolist()
                   if x.filename.replace('\\', '/').split('/')[-1].lower() == 'nvngx_dlssnr.dll']
        if len(entries) != 1 or entries[0].file_size != 165830144:
            raise ValueError('Unexpected runtime archive contents')
        with bundle.open(entries[0]) as source, destination.open('xb') as target:
            shutil.copyfileobj(source, target)
    if digest(destination) != DLL_SHA:
        raise ValueError('Runtime DLL checksum mismatch')
    print('Candidate hashes verified; no DLL loaded during preparation.')


if __name__ == '__main__':
    main()

