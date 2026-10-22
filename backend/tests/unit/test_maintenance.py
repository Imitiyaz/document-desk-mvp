"""Maintenance safety checks for complete offline workspace copies.
Author: Imitiyaz and AI Agent
"""

import io
import tarfile

import pytest

from app.maintenance import backup, restore


def test_complete_workspace_backup_restore_preserves_vectors_and_ledger(tmp_path):
    source = tmp_path / "source"
    (source / "vectors").mkdir(parents=True)
    (source / "records.sqlite3").write_bytes(b"ledger-fixture")
    (source / "vectors" / "segment.bin").write_bytes(b"vector-fixture")
    archive = tmp_path / "backup.tar.gz"
    backup(source, archive)
    target = tmp_path / "restored"
    restore(archive, target)
    assert {
        p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()
    } == {
        p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()
    }
    with pytest.raises(ValueError, match="not empty"):
        restore(archive, target)
    with pytest.raises(ValueError, match="already exists"):
        backup(source, archive)


@pytest.mark.parametrize(
    "name,kind",
    [
        ("../escape", "file"),
        ("workspace/../../escape", "file"),
        ("/workspace/escape", "file"),
        ("workspace/link", "link"),
        ("workspace\\escape", "file"),
    ],
)
def test_unsafe_archive_is_rejected_before_writing(tmp_path, name, kind):
    archive = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        member = tarfile.TarInfo(name)
        if kind == "link":
            member.type = tarfile.SYMTYPE
            member.linkname = "/tmp/escape"
            tar.addfile(member)
        else:
            member.size = 1
            tar.addfile(member, io.BytesIO(b"x"))
    destination = tmp_path / "empty"
    with pytest.raises(ValueError, match="unsafe"):
        restore(archive, destination)
    assert not destination.exists()


def test_backup_inside_source_is_refused(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        backup(tmp_path, tmp_path / "backup.tar.gz")


def test_binary_stream_cli_round_trip_without_bind_mount_permissions(tmp_path):
    import subprocess
    import sys

    source = tmp_path / "source"
    source.mkdir()
    (source / "ledger.sqlite3").write_bytes(b"complete-ledger-fixture")
    output = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.maintenance",
            "backup",
            "--workspace",
            str(source),
            "--archive",
            "-",
        ],
        capture_output=True,
        check=True,
    )
    assert output.stdout.startswith(b"\x1f\x8b")
    target = tmp_path / "restored"
    restored = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.maintenance",
            "restore",
            "--workspace",
            str(target),
            "--archive",
            "-",
        ],
        input=output.stdout,
        capture_output=True,
        check=True,
    )
    assert restored.returncode == 0
    assert (target / "ledger.sqlite3").read_bytes() == b"complete-ledger-fixture"
