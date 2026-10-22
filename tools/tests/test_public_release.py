"""Keep public release notes separate from private development history.

Author: Imitiyaz and AI Agent
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "public_guards", Path(__file__).resolve().parents[1] / "check_repository.py"
)
GUARDS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARDS)


class PublicReleaseTests(unittest.TestCase):
    def test_old_internal_changelog_entries_are_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## 0.3.8 — Initial public release\n\n"
                "## 0.3.7 — Internal work\n",
                encoding="utf-8",
            )
            self.assertTrue(GUARDS.inspect_public_release(root))

    def test_history_leaks_in_other_documents_are_detected(self):
        for phrase in (
            "9.9.9-public.1",
            "as you requested",
            "https://github.com/example/project-private",
        ):
            with self.subTest(phrase=phrase), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "README.md").write_text(phrase, encoding="utf-8")
                self.assertTrue(GUARDS.inspect_public_release(root))

    def test_useful_limits_and_author_lessons_are_not_treated_as_history_leaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CHANGELOG.md").write_text(
                "# Changelog\n\n## 0.3.8 — Initial public release\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text(
                "I learned to verify operands. Current capacity is unmeasured.",
                encoding="utf-8",
            )
            self.assertEqual(GUARDS.inspect_public_release(root), [])


if __name__ == "__main__":
    unittest.main()
