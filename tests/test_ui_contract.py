"""Static regressions, not a substitute for running Blender on Windows."""
import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class UIContractTests(unittest.TestCase):
    def test_viewport_never_spawns_or_saves_project(self):
        source = (ROOT / 'addon/cycles_dlss5/preview_launch.py').read_text(encoding='utf-8')
        for forbidden in ('area_dupli', 'open_preview', 'display_target', 'subprocess', 'Popen', 'save_as_mainfile', 'mkdtemp', 'open_mainfile'):
            self.assertNotIn(forbidden, source)

    def test_style_does_not_claim_relaunch_application(self):
        source = (ROOT / 'addon/cycles_dlss5/styles.py').read_text(encoding='utf-8')
        self.assertNotIn('cycles_dlss5.open_preview', source)
        self.assertIn('Одни параметры NR для обоих режимов', source)

    def test_property_annotations_are_evaluated(self):
        source = (ROOT / "addon/cycles_dlss5/preferences.py").read_text(encoding='utf-8')
        tree = ast.parse(source)
        self.assertFalse(any(isinstance(n, ast.ImportFrom) and n.module == "__future__"
                             and any(a.name == "annotations" for a in n.names)
                             for n in tree.body))

    def test_full_result_and_shared_native_consumer(self):
        final = (ROOT / 'addon/cycles_dlss5/final_render.py').read_text(encoding='utf-8')
        preview = (ROOT / 'addon/cycles_dlss5/viewport.py').read_text(encoding='utf-8')
        self.assertNotIn('_comparison_image', final)
        self.assertNotIn("area.type = 'IMAGE_EDITOR'", final)
        self.assertIn('result_viewer.show(context, _last_image)', final)
        self.assertNotIn("mode='FINAL'", final)
        viewer = (ROOT / 'addon/cycles_dlss5/result_viewer.py').read_text(encoding='utf-8')
        self.assertIn("_area.type = 'IMAGE_EDITOR'", viewer)
        for source in (preview, final):
            self.assertIn('from .frame_job import FrameJob', source)
            self.assertIn('from .styles import values', source)
        self.assertIn('@persistent\ndef scene_changed', preview)

    def test_shortcut_help_only_used_keys(self):
        source = (ROOT / 'addon/cycles_dlss5/preview_launch.py').read_text(encoding='utf-8')
        self.assertNotIn('F5', source)
        self.assertNotIn('F10', source)

    def test_output_is_explicit_and_does_not_overwrite(self):
        source = (ROOT / 'addon/cycles_dlss5/output.py').read_text(encoding='utf-8')
        self.assertIn("destination.open('xb')", source)
        self.assertIn("scene.view_settings.view_transform = 'Standard'", source)
        self.assertIn('context.window_manager.fileselect_add(self)', source)
        self.assertIn("image.file_format not in FORMATS", source)
        self.assertNotIn('output_destination', source)
        final = (ROOT / 'addon/cycles_dlss5/final_render.py').read_text(encoding='utf-8')
        self.assertIn("_request = output.snapshot(context.scene, 'DISK')", final)

    def test_native_paths_match_patch(self):
        backend = (ROOT / "addon/cycles_dlss5/backend.py").read_text()
        patch = (ROOT / "patches/blender-v5.2.1-dlss5nr.patch").read_text()
        for key in ("CYCLES_DLSS5NR_RUNTIME", "CYCLES_DLSS5NR_BRIDGE"):
            self.assertIn(key, backend)
            self.assertIn(key, patch)
        self.assertIn("add_auto_pass(scene, PASS_DEPTH)", patch)
        self.assertIn("currently requires native resolution", patch)
