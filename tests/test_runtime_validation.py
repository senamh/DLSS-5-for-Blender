import tempfile
import unittest
import importlib.util
import sys
import struct
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "addon/cycles_dlss5/runtime_validation.py"
SPEC = importlib.util.spec_from_file_location("runtime_validation", MODULE_PATH)
runtime_validation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = runtime_validation
SPEC.loader.exec_module(runtime_validation)

MIN_RUNTIME_BYTES = runtime_validation.MIN_RUNTIME_BYTES
classify_rtx = runtime_validation.classify_rtx
is_primary_target = runtime_validation.is_primary_target
validate_runtime = runtime_validation.validate_runtime


class RuntimeValidationTests(unittest.TestCase):
    def test_gpu_architecture_selection(self):
        self.assertEqual(classify_rtx("NVIDIA GeForce RTX 4060"), "ADA")
        self.assertEqual(classify_rtx("NVIDIA GeForce RTX 4070"), "ADA")
        self.assertEqual(classify_rtx("NVIDIA GeForce RTX 4070 Laptop GPU"), "ADA")
        self.assertEqual(classify_rtx("NVIDIA GeForce RTX 5060"), "BLACKWELL")
        self.assertEqual(classify_rtx("NVIDIA GeForce RTX 3090"), "TURING_PLUS")
        self.assertEqual(classify_rtx("NVIDIA GTX 1080"), "UNKNOWN")

    def test_rtx_5070_is_the_primary_validation_target(self):
        self.assertTrue(is_primary_target("NVIDIA GeForce RTX 5070"))
        self.assertTrue(is_primary_target("NVIDIA GeForce RTX 5070 Laptop GPU"))
        self.assertFalse(is_primary_target("NVIDIA GeForce RTX 4060"))
        self.assertFalse(is_primary_target("NVIDIA GeForce RTX 4070"))

    def test_missing_runtime_is_actionable(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(FileNotFoundError, "nvngx_dlssnr.dll"):
                validate_runtime(directory)

    def test_non_pe_runtime_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "nvngx_dlssnr.dll"
            runtime.write_bytes(b"NO" + b"\0" * MIN_RUNTIME_BYTES)
            with self.assertRaisesRegex(ValueError, "not a Windows PE"):
                validate_runtime(directory)

    def test_valid_unknown_runtime_gets_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "nvngx_dlssnr.dll"
            data = bytearray(MIN_RUNTIME_BYTES)
            data[:2] = b"MZ"
            struct.pack_into("<I", data, 60, 128)
            data[128:132] = b"PE\0\0"
            struct.pack_into("<H", data, 132, 0x8664)
            struct.pack_into("<H", data, 150, 0x2000)
            struct.pack_into("<H", data, 152, 0x20B)
            runtime.write_bytes(data)
            report = validate_runtime(directory)
            self.assertTrue(report.valid_pe)
            self.assertFalse(report.recognized)
            self.assertEqual(len(report.sha256), 64)


if __name__ == "__main__":
    unittest.main()

