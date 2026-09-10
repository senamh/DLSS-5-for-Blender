"""Relocatable runtime discovery; no downloads or installation into Blender."""
import hashlib
import os
from pathlib import Path
import platform
import sys


def resolve(runtime='', host='', *, addon=None, environ=None, system=None):
    env = os.environ if environ is None else environ
    if (sys.platform if system is None else system) != 'win32':
        raise ValueError('NR требует Windows x64 и совместимую NVIDIA RTX; этот компьютер не поддержан')
    base = Path(addon) if addon is not None else Path(__file__).parent
    candidates = []
    if runtime:
        candidates.append(Path(runtime))
    else:
        if env.get('DLSS5_RUNTIME_DIR'):
            candidates.append(Path(env['DLSS5_RUNTIME_DIR']))
        candidates.append(base / 'runtime')
        if env.get('LOCALAPPDATA'):
            data = Path(env['LOCALAPPDATA']) / 'DLSS-Blender'
            candidates.append(data / 'runtime')
            # Read-only compatibility with previous local preview installations.
            if data.is_dir():
                candidates.extend(sorted(data.glob('preview-*'), reverse=True))
    from .frame_job import RUNTIMES
    for folder in candidates:
        executable = Path(host) if host else folder / 'dlss5-feed-host64.exe'
        if not host and not executable.is_file():
            executable = folder / 'frame-host/dlss5-feed-host64.exe'
        if executable.is_file() and all((folder / name).is_file() for name in RUNTIMES):
            return executable, folder
    raise ValueError('Комплект NR не найден. Preferences → Cycles DLSS 5 → Папка runtime. См. инструкцию установки')


def verify_files(host, folder):
    from .frame_job import RUNTIMES
    for name, (_, digest) in RUNTIMES.items():
        if hashlib.sha256((Path(folder) / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Непроверенная версия runtime: ' + name)
    if not Path(host).is_file():
        raise ValueError('Frame host отсутствует')
    return 'Файлы runtime проверены. Совместимость GPU подтверждается только успешной обработкой NR.'


def gpu_info():
    import shutil
    import subprocess
    if sys.platform != 'win32' or platform.machine().lower() not in {'amd64', 'x86_64'}:
        return 'NR: требуется Windows x64; AMD/Intel/Apple GPU не поддержаны.'
    tool = shutil.which('nvidia-smi')
    if not tool:
        return 'NVIDIA GPU не определена; проверьте драйвер. Проверенная карта: RTX 5070.'
    try:
        result = subprocess.run([tool, '--query-gpu=name,driver_version,memory.total', '--format=csv,noheader'],
                                capture_output=True, text=True, timeout=5,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        return result.stdout.strip() if result.returncode == 0 else 'NVIDIA driver diagnostic failed'
    except (OSError, subprocess.TimeoutExpired):
        return 'Не удалось прочитать GPU; это не подтверждение совместимости.'
