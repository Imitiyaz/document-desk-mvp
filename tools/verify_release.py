"""One controlled release batch with explicit reports and isolated browser storage.

Run from a separate review checkout. Requires a lightweight test environment and
installed frontend dependencies/browser. Does not install packages, reset data,
commit, push, or publish. Docker/native models are a separate verification mode.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-python", default=sys.executable)
    parser.add_argument(
        "--skip-browser",
        action="store_true",
        help="Record browser verification as pending, not passed",
    )
    args = parser.parse_args()
    out = ROOT / "reports/release" / datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(parents=True)
    env = dict(
        os.environ,
        PYTHONUTF8="1",
        ANONYMIZED_TELEMETRY="False",
        OTEL_SDK_DISABLED="true",
        DO_NOT_TRACK="1",
        RAG_TEST_VECTOR_BACKEND="fake",
        PYTHON_EXECUTABLE=str(Path(args.test_python).resolve()),
    )
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    summary: dict = {
        "application_version": "0.3.8",
        "source_revision": json.loads(
            (ROOT / "release.json").read_text(encoding="utf-8")
        ).get("source_revision", "not_recorded"),
        "mode": "controlled_regression_not_native_capacity",
        "checks": [],
        "browser": "pending",
    }
    browser_output = ROOT / "frontend/test-results"
    # A fresh result folder cannot accidentally include a report from a previous run.
    if browser_output.exists():
        browser_output.rename(
            browser_output.with_name("test-results-prior-" + out.name)
        )
    commands = [
        ("repository", [args.test_python, "tools/check_repository.py"], ROOT),
        ("catalog", [args.test_python, "tools/catalog.py", "--check"], ROOT),
        (
            "source-tools",
            [args.test_python, "-m", "unittest", "discover", "-s", "tools/tests", "-v"],
            ROOT,
        ),
        (
            "backend",
            [
                args.test_python,
                "tools/offline_pytest.py",
                "-q",
                "--junitxml=" + str(out / "backend-junit.xml"),
            ],
            ROOT / "backend",
        ),
        (
            "mypy",
            [args.test_python, "-m", "mypy", "app", "--ignore-missing-imports"],
            ROOT / "backend",
        ),
        (
            "ruff",
            [args.test_python, "-m", "ruff", "check", "app", "tests", "tools"],
            ROOT / "backend",
        ),
        (
            "black",
            [args.test_python, "-m", "black", "--check", "app", "tests", "tools"],
            ROOT / "backend",
        ),
    ]
    if npm:
        commands += [
            (name, [npm, "run", script] + extra, ROOT / "frontend")
            for name, script, extra in [
                ("frontend-types", "typecheck", []),
                ("browser-types", "typecheck:browser-contract", []),
                ("frontend-lint", "lint", []),
                ("frontend-tests", "test:coverage", ["--", "--maxWorkers=1"]),
                ("ui-checkers", "test:ui-checker", []),
                ("frontend-build", "build", []),
            ]
        ]
        if not args.skip_browser:
            commands.append(
                ("desktop-browser", [npm, "run", "test:desktop"], ROOT / "frontend")
            )
    try:
        if not npm:
            raise RuntimeError("npm was not found")
        for name, command, cwd in commands:
            with (out / (name + ".txt")).open("w", encoding="utf-8") as log:
                completed = subprocess.run(
                    command,
                    cwd=cwd,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=1200,
                )
            passed = completed.returncode == 0
            summary["checks"].append(
                {"name": name, "passed": passed, "returncode": completed.returncode}
            )
            print(name + (": PASS" if passed else ": FAILED"), flush=True)
            if not passed:
                raise RuntimeError(name + " failed; see its saved log")
            if name == "desktop-browser":
                summary["browser"] = "passed"
        summary["status"] = (
            "passed_with_browser_pending" if args.skip_browser else "passed"
        )
    except Exception as exc:
        summary["status"] = "failed"
        summary["error"] = type(exc).__name__ + ": " + str(exc)
        print(summary["error"], flush=True)
    finally:
        if browser_output.exists():
            shutil.copytree(browser_output, out / "browser", dirs_exist_ok=True)
        (out / "summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )
        archive = out.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for p in out.rglob("*"):
                if p.is_file() and "mypy-cache" not in p.relative_to(out).parts:
                    z.write(p, p.relative_to(out))
        print("REPORT ZIP: " + str(archive), flush=True)
    return int(summary["status"] == "failed")


if __name__ == "__main__":
    raise SystemExit(main())
