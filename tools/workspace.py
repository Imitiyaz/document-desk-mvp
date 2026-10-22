"""Offline Compose backup/restore through streams, avoiding host UID/bind issues.

Stop every API writer first. Restore refuses a nonempty target via the in-image
maintenance guard. Original volumes are never removed by this helper.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compose_command(project: str) -> list[str]:
    """Avoid ambient COMPOSE_FILE/cwd redirecting maintenance to another stack."""
    return [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "-f",
        str(ROOT / "compose.yaml"),
        "-p",
        project,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore"])
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    if not args.project_name.startswith("rag-mvp-review"):
        parser.error("Use a dedicated project name beginning rag-mvp-review")
    compose = compose_command(args.project_name)
    running = subprocess.run(
        compose + ["ps", "--status", "running", "--services"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    if "backend" in running:
        raise RuntimeError("Stop the backend before backup/restore; no files changed")
    command = compose + [
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "backend",
        "python",
        "-m",
        "app.maintenance",
        args.action,
        "--archive",
        "-",
    ]
    if args.action == "backup":
        if args.archive.exists():
            raise RuntimeError("Backup path already exists")
        args.archive.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.archive.open("xb") as output:
                result = subprocess.run(command, cwd=ROOT, stdout=output)
            if result.returncode:
                raise RuntimeError("Backup process failed")
            with args.archive.open("rb") as stream:
                if stream.read(2) != b"\x1f\x8b":
                    raise RuntimeError("Backup output is not a gzip archive")
        except Exception:
            args.archive.unlink(missing_ok=True)
            raise
    else:
        with args.archive.open("rb") as source:
            result = subprocess.run(command, cwd=ROOT, stdin=source)
        if result.returncode:
            raise RuntimeError(
                "Restore process failed; keep original volumes and inspect the isolated restore target"
            )
    print(args.action.upper() + " COMPLETE: " + str(args.archive.resolve()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
