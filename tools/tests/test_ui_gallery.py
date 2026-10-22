"""Protect reviewed UI assets from failed or unsafe capture promotion.

Author: Imitiyaz and AI Agent
"""

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("gallery", ROOT / "tools/ui_gallery.py")
GALLERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GALLERY)


class UIGalleryTests(unittest.TestCase):
    def fixture(self, folder):
        root = folder / "source"
        target = root / GALLERY.ASSETS
        target.parent.mkdir(parents=True)
        shutil.copytree(ROOT / GALLERY.ASSETS, target)
        (root / "docs/ui.md").write_text(
            (ROOT / "docs/ui.md").read_text(encoding="utf-8"), encoding="utf-8"
        )
        run = folder / "capture run"
        run.mkdir()
        shutil.copyfile(target / "desktop-lookup.png", run / "1920-lookup.png")
        manifest = {
            "application_version": "0.3.8",
            "operator_mode": "actual_model_required_for_narrative",
            "viewport": {"width": 1920},
            "captures": [
                {
                    "scenario": "lookup",
                    "status": "passed",
                    "validation_status": "passed",
                    "file": "1920-lookup.png",
                }
            ],
        }
        (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return root, run, manifest

    def test_shipped_images_and_gallery_are_consistent(self):
        self.assertEqual(GALLERY.check(ROOT), [])

    def test_missing_review_confirmation_never_changes_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, run, _ = self.fixture(Path(tmp))
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with self.assertRaisesRegex(ValueError, "--reviewed"):
                GALLERY.promote(run, ["lookup"], False, root)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            self.assertFalse((root / "reports").exists())

    def test_failed_or_ambiguous_capture_is_rejected_before_writes(self):
        for mutation in ("status", "validation_status", "duplicate", "mode", "width"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root, run, manifest = self.fixture(Path(tmp))
                if mutation in {"status", "validation_status"}:
                    manifest["captures"][0][mutation] = "failed"
                elif mutation == "duplicate":
                    manifest["captures"].append(dict(manifest["captures"][0]))
                elif mutation == "mode":
                    manifest["operator_mode"] = "scripted"
                else:
                    manifest["viewport"]["width"] = 1440
                (run / "manifest.json").write_text(
                    json.dumps(manifest), encoding="utf-8"
                )
                with self.assertRaises(ValueError):
                    GALLERY.promote(run, ["lookup"], True, root)
                self.assertEqual(GALLERY.check(root), [])
                self.assertFalse((root / "reports").exists())

    def test_capture_path_traversal_and_windows_stream_names_are_rejected(self):
        for name in ("../secret.png", r"..\secret.png", "image.png:private", "/x.png"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root, run, manifest = self.fixture(Path(tmp))
                manifest["captures"][0]["file"] = name
                (run / "manifest.json").write_text(
                    json.dumps(manifest), encoding="utf-8"
                )
                with self.assertRaisesRegex(ValueError, "basename"):
                    GALLERY.promote(run, ["lookup"], True, root)
                self.assertFalse((root / "reports").exists())

    def test_invalid_or_truncated_png_is_rejected_before_writes(self):
        for raw in (b"not an image", b"\x89PNG\r\n\x1a\n"):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as tmp:
                root, run, _ = self.fixture(Path(tmp))
                (run / "1920-lookup.png").write_bytes(raw)
                with self.assertRaises(ValueError):
                    GALLERY.promote(run, ["lookup"], True, root)
                self.assertFalse((root / "reports").exists())

    def test_promotion_backs_up_gallery_and_keeps_raw_capture_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, run, _ = self.fixture(Path(tmp))
            original = (root / "docs/ui.md").read_bytes()
            raw = (run / "manifest.json").read_bytes()
            backup = GALLERY.promote(run, ["lookup"], True, root)
            self.assertEqual(GALLERY.check(root), [])
            self.assertEqual((backup / "0-ui.md").read_bytes(), original)
            self.assertEqual((run / "manifest.json").read_bytes(), raw)
            self.assertIn(
                "actual-model application capture",
                (root / "docs/ui.md").read_text(encoding="utf-8"),
            )

    def test_post_write_validation_failure_restores_exact_originals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, run, _ = self.fixture(Path(tmp))
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            with patch.object(GALLERY, "check", side_effect=[[], ["injected fault"]]):
                with self.assertRaisesRegex(ValueError, "injected fault"):
                    GALLERY.promote(run, ["lookup"], True, root)
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            self.assertEqual(GALLERY.check(root), [])

    def test_changed_gallery_image_or_broken_page_is_detected_without_rewriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, _, _ = self.fixture(Path(tmp))
            page = root / "docs/ui.md"
            page.write_text("broken reference", encoding="utf-8")
            self.assertTrue(GALLERY.check(root))
            self.assertEqual(page.read_text(encoding="utf-8"), "broken reference")
