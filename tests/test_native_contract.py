"""Source regressions; native runtime behavior requires Windows GPU tests."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class NativeContractTests(unittest.TestCase):
    def test_public_header_matches_export_names(self):
        source = (ROOT / 'native/src/dlss5nr_bridge.cpp').read_text()
        header = (ROOT / 'native/include/cycles_dlss5_bridge.h').read_text()
        exports = set(re.findall(r'__cdecl (dlss5nr_\w+)\(', source))
        declarations = set(re.findall(r'\b(dlss5nr_\w+)\(', header))
        self.assertEqual(exports, declarations)
        self.assertIn('#include "cycles_dlss5_bridge.h"', source)

    def test_guides_have_independent_gpu_upload_sources(self):
        source = (ROOT / 'native/src/dlss5nr_bridge.cpp').read_text()
        self.assertIn('g_depth.Get(), g_upload_guide.Get()', source)
        self.assertIn('g_motion.Get(), g_upload_motion.Get()', source)
        self.assertIn('g_upload_motion = CreateLinearBuffer', source)
        self.assertIn('g_upload_motion.Reset()', source)
        self.assertEqual(source.count('if (!UploadGuideTexture('), 2)

    def test_unverified_temporal_mode_is_disabled(self):
        source = (ROOT / 'native/src/dlss5nr_bridge.cpp').read_text()
        self.assertIn('SetEvalParams(1);', source)
        self.assertNotIn('SetEvalParams((!', source)
        self.assertIn('if (g_clients > 1)', source)
        self.assertIn('zero_guides.resize', source)

