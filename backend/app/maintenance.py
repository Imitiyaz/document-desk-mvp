# SPDX-License-Identifier: AGPL-3.0-only
"""Offline workspace backup/restore. Stop all API writers before using this tool.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

MAX_BACKUP_BYTES = 10 * 1024**3
MAX_BACKUP_MEMBERS = 100000


def backup(source: Path, archive: Path) -> None:
    """Copy the complete persistence directory, never an active two-store snapshot."""
    source, archive = source.resolve(), archive.resolve()
    if not source.is_dir():
        raise ValueError("Workspace directory does not exist")
    if archive == source or source in archive.parents:
        raise ValueError("Backup must be outside the workspace")
    if archive.exists():
        raise ValueError("Backup already exists; choose a new filename")
    paths = list(source.rglob("*"))
    if any(p.is_symlink() for p in paths):
        raise ValueError("Workspace contains symlinks; inspect before backup")
    if (
        len(paths) > MAX_BACKUP_MEMBERS
        or sum(p.stat().st_size for p in paths if p.is_file()) > MAX_BACKUP_BYTES
    ):
        raise ValueError("Workspace exceeds maintenance budget")
    archive.parent.mkdir(parents=True, exist_ok=True)
    try:
        with archive.open("xb") as output, tarfile.open(
            fileobj=output, mode="w:gz"
        ) as tar:
            tar.add(source, arcname="workspace", recursive=True)
    except Exception:
        archive.unlink(missing_ok=True)
        raise


def restore(archive: Path, destination: Path) -> None:
    """Validate every archive member before restoring into an empty directory."""
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(
            "Restore destination is not empty; original data was not changed"
        )
    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        if (
            len(members) > MAX_BACKUP_MEMBERS
            or sum(m.size for m in members) > MAX_BACKUP_BYTES
        ):
            raise ValueError("Archive exceeds maintenance budget")
        seen: set[str] = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (
                not path.parts
                or path.parts[0] != "workspace"
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in member.name
                or member.name in seen
                or not (member.isfile() or member.isdir())
            ):
                raise ValueError("Archive has unsafe or duplicate members")
            seen.add(member.name)
        destination.mkdir(parents=True, exist_ok=True)
        # Extract regular files manually. Do not follow links or restore device files.
        for member in members:
            relative = PurePosixPath(member.name).parts[1:]
            target = destination.joinpath(*relative)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                stream = tar.extractfile(member)
                if stream is None:
                    raise ValueError("Archive member has no file content")
                with stream, target.open("xb") as output:
                    shutil.copyfileobj(stream, output)


def main() -> None:
    from app.core.config import settings

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore"])
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument(
        "--workspace", type=Path, default=Path(settings.chroma_persist_dir)
    )
    args = parser.parse_args()
    if str(args.archive) == "-":
        with tempfile.TemporaryDirectory(prefix="rag-maintenance-") as temporary:
            archive = Path(temporary) / "workspace.tar.gz"
            if args.action == "backup":
                backup(args.workspace, archive)
                with archive.open("rb") as stream:
                    shutil.copyfileobj(stream, sys.stdout.buffer)
            else:
                with archive.open("wb") as stream:
                    shutil.copyfileobj(sys.stdin.buffer, stream)
                restore(archive, args.workspace)
        print(
            json.dumps({"status": "complete", "action": args.action}), file=sys.stderr
        )
        return
    if args.action == "backup":
        backup(args.workspace, args.archive)
    else:
        restore(args.archive, args.workspace)
    print(
        json.dumps(
            {"status": "complete", "action": args.action, "archive": str(args.archive)}
        )
    )


if __name__ == "__main__":
    main()
