"""Validation helpers for user-supplied DLSS Neural Rendering runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
import struct


RUNTIME_FILENAME = "nvngx_dlssnr.dll"
MIN_RUNTIME_BYTES = 1_000_000
TARGET_GPU = "NVIDIA GeForce RTX 5070"
TARGET_GPU_PATTERN = re.compile(r"\bRTX\s*5070\b", re.IGNORECASE)


@dataclass(frozen=True)
class RuntimeReport:
    path: Path
    sha256: str
    size: int
    valid_pe: bool
    recognized: bool
    label: str


# Runtime binaries are proprietary and are never included in this repository.
# Add a fingerprint only after it has been reproduced from a documented source.
KNOWN_RUNTIMES: dict[str, str] = {}


def classify_rtx(name: str) -> str:
    """Return the runtime architecture for a recognizable GeForce RTX GPU."""
    match = re.search(r"\bRTX\s*([2-5])\d{3}\b", name.upper())
    if not match:
        return "UNKNOWN"
    generation = match.group(1)
    if generation == "5":
        return "BLACKWELL"
    if generation == "4":
        return "ADA"
    return "TURING_PLUS"


def is_primary_target(name: str) -> bool:
    """Identify the planned test target; this is not compatibility evidence."""
    return bool(TARGET_GPU_PATTERN.search(name))


def validate_runtime(directory: str | Path) -> RuntimeReport:
    path = Path(directory).expanduser() / RUNTIME_FILENAME
    if not path.is_file():
        raise FileNotFoundError(f"{RUNTIME_FILENAME} was not found in {path.parent}")

    size = path.stat().st_size
    if size < MIN_RUNTIME_BYTES:
        raise ValueError(f"{RUNTIME_FILENAME} is unexpectedly small ({size} bytes)")

    with path.open("rb") as stream:
        header = stream.read(64)
        pe_offset = struct.unpack_from("<I", header, 60)[0]
        if header[:2] != b"MZ" or pe_offset < 64 or pe_offset > size - 26:
            raise ValueError(f"{RUNTIME_FILENAME} is not a Windows PE file")
        stream.seek(pe_offset)
        pe = stream.read(26)
        valid_pe = (pe[:4] == b"PE\0\0" and
                    struct.unpack_from("<H", pe, 4)[0] == 0x8664 and
                    struct.unpack_from("<H", pe, 22)[0] & 0x2000 != 0 and
                    struct.unpack_from("<H", pe, 24)[0] == 0x20B)
        stream.seek(0)
        digest = sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)

    if not valid_pe:
        raise ValueError(f"{RUNTIME_FILENAME} is not a Windows PE x64 DLL")

    fingerprint = digest.hexdigest()
    label = KNOWN_RUNTIMES.get(fingerprint, "Unrecognized external runtime")
    return RuntimeReport(path, fingerprint, size, valid_pe, fingerprint in KNOWN_RUNTIMES, label)

