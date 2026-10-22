"""Boundary tests for source navigation and deployment verification helpers.
Author: Imitiyaz and AI Agent
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path, PurePosixPath, PureWindowsPath
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReleaseToolsTests(unittest.TestCase):
    def test_compose_tools_pin_the_checkout_and_file_including_space_paths(self):
        for name in ("workspace", "verify_docker"):
            module = load(name)
            with self.subTest(tool=name), tempfile.TemporaryDirectory(
                prefix="release with spaces "
            ) as temporary:
                root = Path(temporary)
                with patch.object(module, "ROOT", root), patch.dict(
                    "os.environ", {"COMPOSE_FILE": "unrelated-compose.yaml"}
                ):
                    for project in ("rag-mvp-review", "rag-mvp-review-restore-1"):
                        self.assertEqual(
                            module.compose_command(project),
                            [
                                "docker",
                                "compose",
                                "--project-directory",
                                str(root),
                                "-f",
                                str(root / "compose.yaml"),
                                "-p",
                                project,
                            ],
                        )

    def test_catalog_order_is_identical_for_windows_and_posix_paths(self):
        catalog = load("catalog")
        expected = [
            ".github/ISSUE_TEMPLATE/bug_report.md",
            ".github/dependabot.yml",
            "LICENSE",
            "README.md",
            "compose.yaml",
            "frontend/src/App.tsx",
            "frontend/src/api.ts",
            "frontend/src/asset/icon.ts",
            "frontend/src/asset.ts",
        ]
        # Exercise Path's real Windows ordering semantics on every test host;
        # changing os.name alone would leave PosixPath comparisons unchanged.
        for flavor, base in [
            (PurePosixPath, "/review"),
            (PureWindowsPath, "C:/review"),
        ]:
            with self.subTest(platform=flavor.__name__):
                root = flavor(base)
                walk = [
                    (
                        str(root),
                        ["frontend", ".github"],
                        ["compose.yaml", "README.md", "LICENSE"],
                    ),
                    (str(root / ".github"), ["ISSUE_TEMPLATE"], ["dependabot.yml"]),
                    (str(root / ".github/ISSUE_TEMPLATE"), [], ["bug_report.md"]),
                    (
                        str(root / "frontend/src"),
                        ["asset"],
                        ["api.ts", "asset.ts", "App.tsx"],
                    ),
                    (str(root / "frontend/src/asset"), [], ["icon.ts"]),
                ]
                with patch.object(catalog, "Path", flavor), patch.object(
                    catalog.os, "walk", return_value=walk
                ):
                    actual = catalog.paths(root)
                self.assertEqual(
                    [path.relative_to(root).as_posix() for path in actual], expected
                )

    def test_catalog_check_accepts_crlf_without_rewriting_files(self):
        catalog = load("catalog")
        original_write_text = Path.write_text
        # Exercise native LF and native CRLF generation on every host. Merely
        # checking the fixture produced on Linux missed Windows' text translation.
        for native_newline in ("\n", "\r\n"):
            with self.subTest(native_newline=repr(native_newline)):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    (root / "README.md").write_text(
                        "# Test project\n", encoding="utf-8"
                    )

                    def write_native_text(
                        path, text, encoding=None, errors=None, newline=None
                    ):
                        return original_write_text(
                            path,
                            text,
                            encoding=encoding,
                            errors=errors,
                            newline=native_newline if newline is None else newline,
                        )

                    with patch.object(catalog, "ROOT", root), patch(
                        "sys.argv", ["catalog.py"]
                    ), patch.object(Path, "write_text", write_native_text):
                        self.assertEqual(catalog.main(), 0)
                    generated = catalog.render(root)
                    for name, content in generated.items():
                        source = root / name
                        # render() returns canonical LF text. Replacing raw bytes
                        # would turn native CRLF into CRCRLF, adding blank lines.
                        source.write_bytes(
                            content.replace("\n", "\r\n").encode("utf-8")
                        )
                        self.assertNotIn(b"\r\r\n", source.read_bytes())
                    before = {p: p.read_bytes() for p in catalog.paths(root)}
                    with patch.object(catalog, "ROOT", root), patch(
                        "sys.argv", ["catalog.py", "--check"]
                    ):
                        self.assertEqual(catalog.main(), 0)
                    self.assertEqual(
                        before, {p: p.read_bytes() for p in catalog.paths(root)}
                    )

    def test_catalog_check_rejects_real_drift_without_rewriting_files(self):
        catalog = load("catalog")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "README.md").write_text("# Test project\n", encoding="utf-8")
            with patch.object(catalog, "ROOT", root), patch("sys.argv", ["catalog.py"]):
                self.assertEqual(catalog.main(), 0)
            index = root / "docs/index.md"
            index.write_text(
                index.read_text(encoding="utf-8") + "\nChanged.\n", encoding="utf-8"
            )
            before = {p: p.read_bytes() for p in catalog.paths(root)}
            with patch.object(catalog, "ROOT", root), patch(
                "sys.argv", ["catalog.py", "--check"]
            ):
                self.assertEqual(catalog.main(), 1)
            self.assertEqual(before, {p: p.read_bytes() for p in catalog.paths(root)})

    def test_catalog_includes_hidden_configuration_and_excludes_user_data(self):
        catalog = load("catalog")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in [
                "README.md",
                ".gitignore",
                ".env.example",
                "backend/app/main.py",
                "data/private.pdf",
                "frontend/test-results-prior-old/private.txt",
                ".env",
                "frontend/node_modules/private.js",
            ]:
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("# Example\n")
            self.assertEqual(
                {p.relative_to(root).as_posix() for p in catalog.paths(root)},
                {"README.md", ".gitignore", ".env.example", "backend/app/main.py"},
            )

    def test_inventory_assigns_each_file_exactly_once(self):
        catalog = load("catalog")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Real purpose\n")
            result = json.loads(catalog.render(root)["docs/catalog/files.json"])
            self.assertEqual(
                result["files"],
                [
                    {
                        "path": "README.md",
                        "category": "project",
                        "purpose": "Real purpose",
                    }
                ],
            )

    def test_docker_runner_refuses_nonreview_project_before_mutation(self):
        runner = load("verify_docker")
        with patch(
            "sys.argv", ["verify_docker.py", "--project-name", "ordinary-workspace"]
        ), patch.object(runner.subprocess, "run") as run:
            with self.assertRaises(SystemExit):
                runner.main()
            run.assert_not_called()

    def test_docker_runner_refuses_nonloopback_endpoint(self):
        runner = load("verify_docker")
        with patch(
            "sys.argv",
            [
                "verify_docker.py",
                "--project-name",
                "rag-mvp-review",
                "--base-url",
                "https://example.com",
            ],
        ), patch.object(runner.subprocess, "run") as run:
            with self.assertRaises(SystemExit):
                runner.main()
            run.assert_not_called()

    def test_catalog_groups_unknown_new_files_instead_of_omitting_them(self):
        catalog = load("catalog")
        self.assertEqual(catalog.category("future-component.txt"), "project")
        self.assertEqual(catalog.category("backend/app/new.py"), "backend")
        self.assertEqual(catalog.category("tools/new.py"), "delivery")

    def test_container_maintenance_module_is_importable_from_declared_workdir(self):
        import os
        import re
        import shutil
        import subprocess
        import sys

        root = TOOLS.parent
        dockerfile = (root / "backend/Dockerfile").read_text()
        configured = re.search(r"PYTHONPATH=(\S+)", dockerfile).group(1)
        self.assertEqual(configured, "/app/backend")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            shutil.copytree(
                root / "backend/app",
                target / "backend/app",
                ignore=shutil.ignore_patterns("__pycache__"),
            )
            env = dict(os.environ, PYTHONPATH=str(target / "backend"))
            # No third-party dependencies are needed for module import; actual
            # maintenance commands are covered separately in backend tests.
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import app.maintenance; print(callable(app.maintenance.backup))",
                ],
                cwd=target,
                env=env,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(completed.stdout.strip(), "True")

    def test_multiline_jsdoc_produces_a_meaningful_nonempty_file_description(self):
        catalog = load("catalog")
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "App.tsx"
            source.write_text(
                "/**\n * Coordinate document selection and safe lifecycle actions.\n * Author: Example\n */\nexport default null;\n"
            )
            self.assertEqual(
                catalog.purpose(source),
                "Coordinate document selection and safe lifecycle actions",
            )


if __name__ == "__main__":
    unittest.main()
