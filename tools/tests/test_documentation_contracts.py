"""Prevent missing README figures, attribution drift and misleading labels.

Author: Imitiyaz and AI Agent
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "repository_guards", Path(__file__).resolve().parents[1] / "check_repository.py"
)
GUARDS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARDS)


class DocumentationContractsTests(unittest.TestCase):
    def fixture(self, root, body, source="ARCHITECTURE.md"):
        (root / "docs").mkdir()
        title = "**Figure TEST-01 — Source flow.**\n\n"
        block = title + "```mermaid\n" + body + "```\n"
        (root / "README.md").write_text("# Runtime\n\n" + block, encoding="utf-8")
        if source != "README.md":
            (root / source).write_text("# Runtime\n\n" + block, encoding="utf-8")
        (root / "docs/diagrams.md").write_text(
            "# Diagram index\n\nRead the README gallery.\n", encoding="utf-8"
        )
        (root / "docs/diagram-register.json").write_text(
            json.dumps(
                [
                    {
                        "id": "TEST-01",
                        "title": "Source flow",
                        "source": source,
                        "kind": "Flowchart",
                        "anchor": "runtime",
                    }
                ]
            ),
            encoding="utf-8",
        )

    def test_readme_displays_exact_registered_context_source(self):
        for source in ("README.md", "ARCHITECTURE.md"):
            with self.subTest(
                source=source
            ), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.fixture(root, 'flowchart TD\n A -->|"Send question"| B\n', source)
                self.assertEqual(GUARDS.inspect_diagrams(root), [])

    def test_multiline_markdown_labels_are_valid_and_not_counted_as_missing_edges(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(
                root,
                'flowchart TD\n A["`Source\nrecords`"] -->|"`Read complete\npopulation`"| B{"`Evidence\nsupported?`"}\n',
            )
            self.assertEqual(GUARDS.inspect_diagrams(root), [])

    def test_missing_or_unlabeled_flow_is_rejected(self):
        bodies = [
            "flowchart TD\n A --> B\n",
            'flowchart TD\n A -->|"Send question"| B --> C\n',
            "stateDiagram-v2\n Ready --> [*]\n",
            "sequenceDiagram\n A->>B\n",
        ]
        for body in bodies:
            with self.subTest(body=body), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.fixture(root, body)
                self.assertTrue(
                    any("Unlabeled" in f for f in GUARDS.inspect_diagrams(root))
                )

    def test_context_or_readme_changes_cannot_drift_silently(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root, 'flowchart TD\n A -->|"Upload bytes"| B\n')
            source = root / "ARCHITECTURE.md"
            source.write_text(
                source.read_text().replace("Upload bytes", "Discard bytes")
            )
            self.assertTrue(
                any("README figure differs" in f for f in GUARDS.inspect_diagrams(root))
            )
            (root / "README.md").write_text("# Empty\n")
            self.assertTrue(
                any("cover every" in f for f in GUARDS.inspect_diagrams(root))
            )

    def test_large_unwrapped_decision_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(
                root,
                'flowchart TD\n A -->|"Inspect"| B{"Is the requested literal subject supported?"}\n',
            )
            self.assertTrue(
                any(
                    "Unwrapped long decision" in f
                    for f in GUARDS.inspect_diagrams(root)
                )
            )

    def test_figure_requires_caption_and_complete_register(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root, 'flowchart TD\n A -->|"Read"| B\n')
            readme = root / "README.md"
            readme.write_text(
                readme.read_text().replace("**Figure TEST-01 — Source flow.**\n\n", "")
            )
            self.assertTrue(any("Untitled" in f for f in GUARDS.inspect_diagrams(root)))
            (root / "docs/diagram-register.json").write_text("not JSON")
            self.assertTrue(any("Invalid" in f for f in GUARDS.inspect_diagrams(root)))

    def test_sequence_caption_rejects_unescaped_statement_separator(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root, "sequenceDiagram\n A->>B: Write facts; publish ready\n")
            self.assertTrue(
                any(
                    "Unsafe sequence separator" in x
                    for x in GUARDS.inspect_diagrams(root)
                )
            )

    def test_documentation_and_decisions_require_explicit_human_ownership(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "docs/decisions").mkdir(parents=True)
            path = root / "docs/decisions/local.md"
            path.write_text("# Decision\n\nAuthor: Imitiyaz and AI Agent\n")
            self.assertEqual(len(GUARDS.inspect_attribution(root)), 2)
            path.write_text(
                "# Decision\n\nAuthor: **Imitiyaz**. AI assistance: **AI Agent**.\n\nDecision owner and approver: **Imitiyaz**.\n"
            )
            self.assertEqual(GUARDS.inspect_attribution(root), [])

    def test_table_captions_are_required_but_code_examples_are_not_tables(self):
        table = "| Area | Purpose |\n| --- | --- |\n| API | Answer |\n"
        self.assertEqual(
            GUARDS.inspect_table_captions(
                "**Table TEST-T01 — Responsibilities.**\n\n" + table, "test.md"
            ),
            [],
        )
        self.assertTrue(GUARDS.inspect_table_captions(table, "test.md"))
        self.assertEqual(
            GUARDS.inspect_table_captions("```text\n" + table + "```\n", "test.md"), []
        )


if __name__ == "__main__":
    unittest.main()
