"""Windows loader smoke check. Never initializes NGX or loads its runtime."""
import argparse
import ctypes
import sys
from pathlib import Path

EXPORTS = (
    'dlss5nr_version', 'dlss5nr_abi_info', 'dlss5nr_gpu_name',
    'dlss5nr_color_codec_version', 'dlss5nr_init', 'dlss5nr_process', 'dlss5nr_process_guided', 'dlss5nr_shutdown',
)
SHIM_EXPORTS = (
    'DLSSNR_LoadSnippet', 'DLSSNR_CallInit', 'DLSSNR_CallCreate',
    'DLSSNR_CallEvaluate', 'DLSSNR_CallRelease', 'DLSSNR_CallShutdown',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('Run on Windows x64 after building the native libraries')
    for name, exports in (
        ('dlss5nr_bridge.dll', EXPORTS),
        ('nvngx.dll_blender.dll', SHIM_EXPORTS),
    ):
        dll = ctypes.CDLL(str((args.directory / name).resolve(strict=True)))
        for symbol in exports:
            getattr(dll, symbol)
        print(f'{name}: {len(exports)} exports found; neural execution NOT tested')


if __name__ == '__main__':
    main()

