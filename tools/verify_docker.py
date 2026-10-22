"""Verify a dedicated, empty Compose review project without touching native data.

Requires running containers built from this release and an installed host model.
Does not delete volumes, modify firewalls, or stop host Ollama.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from urllib.parse import urlsplit
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def compose_command(project: str) -> list[str]:
    """Bind every main/restore command to this checkout's reviewed Compose file."""
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


def request(
    base: str, path: str, data: dict | None = None, method: str = "GET"
) -> dict | list:
    raw = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        base + path,
        data=raw,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.loads(response.read())


def upload(base: str, path: Path, name: str) -> dict:
    boundary = "rag" + uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
        + path.read_bytes()
        + f"\r\n--{boundary}--\r\n".encode()
    )
    req = urllib.request.Request(
        base + "/documents",
        data=body,
        method="POST",
        headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
    )
    with urllib.request.urlopen(req, timeout=240) as response:
        assert response.status == 201
        return json.loads(response.read())


def wait_ready(base: str) -> None:
    deadline = time.monotonic() + 360
    while time.monotonic() < deadline:
        try:
            if request(base, "/ready") == {"status": "ready"}:
                return
        except (OSError, ValueError):
            pass
        time.sleep(2)
    raise TimeoutError("API readiness did not complete")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/api")
    parser.add_argument("--temporary-port", type=int, default=18081)
    args = parser.parse_args()
    if not args.project_name.startswith("rag-mvp-review"):
        parser.error("Use a dedicated project name beginning rag-mvp-review")
    endpoint = urlsplit(args.base_url)
    if (
        endpoint.scheme != "http"
        or endpoint.hostname != "127.0.0.1"
        or endpoint.username
        or endpoint.password
        or endpoint.query
        or endpoint.fragment
        or not endpoint.port
    ):
        parser.error("Only a loopback review deployment is supported")
    if not 1024 <= args.temporary_port < 65535:
        parser.error("Temporary ports must be unprivileged valid ports")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    out = ROOT / "reports/docker" / stamp
    out.mkdir(parents=True)
    report: dict = {
        "version": "0.3.8",
        "started": stamp,
        "checks": [],
        "mode": "real_docker_native_runtime",
        "project": args.project_name,
    }
    compose = compose_command(args.project_name)
    temporary_name = "rag-review-unavailable-" + uuid.uuid4().hex[:10]
    temporary_started = False
    restore_name = "rag-review-restored-" + uuid.uuid4().hex[:10]
    restore_started = False
    main_stopped = False

    def command(arguments: list[str], label: str, timeout: int = 420) -> str:
        result = subprocess.run(
            arguments,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
        (out / (label + ".txt")).write_text(
            result.stdout + result.stderr, encoding="utf-8"
        )
        if result.returncode:
            raise RuntimeError(label + " failed; see its saved log")
        return result.stdout

    def record(label: str, body: object) -> None:
        report["checks"].append({"name": label, "passed": True, "evidence": body})
        print(label + ": PASS")

    try:
        command(compose + ["config", "--quiet"], "compose-config")
        command(compose + ["ps", "--format", "json"], "compose-services")
        command(compose + ["images", "--format", "json"], "compose-images")
        wait_ready(args.base_url)
        info = request(args.base_url, "/openapi.json")
        assert (
            isinstance(info, dict) and info["info"]["version"] == "0.3.8"
        ), "Unexpected API version"
        assert (
            request(args.base_url, "/documents") == []
        ), "Review catalog must be empty; existing documents were not changed"
        suffix = uuid.uuid4().hex[:10]
        sales = "docker-" + suffix + ".xlsx"
        pdf = "docker-" + suffix + ".pdf"
        upload(args.base_url, ROOT / "backend/tests/fixtures/sample_sales.xlsx", sales)
        upload(
            args.base_url,
            ROOT / "backend/tests/fixtures/acceptance/operations.pdf",
            pdf,
        )
        body = request(
            args.base_url,
            "/query",
            {
                "question": "What was the Q3 revenue for North in the Q3 Sales sheet?",
                "source_file": sales,
            },
            "POST",
        )
        assert isinstance(body, dict) and [
            (r["values"]["Q3 Revenue"], r["cell_references"]["Q3 Revenue"])
            for r in body["records"]
        ] == [("45000", "B2")]
        record("exact-lookup-and-cell", body)
        command(
            compose + ["up", "-d", "--no-deps", "--force-recreate", "backend"],
            "recreate-backend",
        )
        # Query the same proxy after recreation; DNS/proxy recovery is part of this test.
        wait_ready(args.base_url)
        catalog = request(args.base_url, "/documents")
        assert isinstance(catalog, list) and {d["source_file"] for d in catalog} == {
            sales,
            pdf,
        }
        record("persistence-after-recreation", catalog)
        after = request(
            args.base_url,
            "/query",
            {
                "question": "What was the Q3 revenue for North in the Q3 Sales sheet?",
                "source_file": sales,
            },
            "POST",
        )
        assert isinstance(after, dict) and after["records"] == body["records"]
        record("persisted-source-provenance", after)
        main_stopped = True
        command(compose + ["stop", "backend"], "stop-for-maintenance")
        backups = out / "backup"
        backups.mkdir()
        archive_path = backups / "workspace.tar.gz"
        command(
            [
                sys.executable,
                "tools/workspace.py",
                "backup",
                "--project-name",
                args.project_name,
                "--archive",
                str(archive_path),
            ],
            "complete-workspace-backup",
        )
        assert archive_path.is_file()
        record("offline-complete-workspace-backup", {"archive_created": True})
        restored_project = args.project_name + "-restore-" + suffix
        command(
            [
                sys.executable,
                "tools/workspace.py",
                "restore",
                "--project-name",
                restored_project,
                "--archive",
                str(archive_path),
            ],
            "isolated-workspace-restore",
        )
        restored_compose = compose_command(restored_project)
        restore_started = True
        command(
            restored_compose
            + [
                "run",
                "-d",
                "--no-deps",
                "--name",
                restore_name,
                "-v",
                args.project_name + "_model_cache:/app/shared-cache",
                "-e",
                "HF_HOME=/app/shared-cache/huggingface",
                "-p",
                f"127.0.0.1:{args.temporary_port+1}:8000",
                "backend",
            ],
            "start-restored-api",
        )
        restore_started = True
        restored_url = f"http://127.0.0.1:{args.temporary_port+1}"
        wait_ready(restored_url)
        restored_answer = request(
            restored_url,
            "/query",
            {
                "question": "What was the Q3 revenue for North in the Q3 Sales sheet?",
                "source_file": sales,
            },
            "POST",
        )
        assert (
            isinstance(restored_answer, dict)
            and restored_answer["records"] == body["records"]
        )
        record(
            "isolated-restored-source-provenance",
            {"response": restored_answer, "retained_restore_project": restored_project},
        )
        command(["docker", "stop", restore_name], "stop-restored-api")
        command(["docker", "rm", restore_name], "remove-restored-container")
        restore_started = False
        command(
            compose
            + [
                "run",
                "--rm",
                "--no-deps",
                "--entrypoint",
                "python",
                "backend",
                "-c",
                "import urllib.request; print(urllib.request.urlopen('http://host.docker.internal:11434/api/tags',timeout=10).status)",
            ],
            "host-ollama-connection",
        )
        # A one-off API runs only while the normal writer is stopped. Host Ollama is untouched.
        temporary_started = True
        command(
            compose
            + [
                "run",
                "-d",
                "--no-deps",
                "--name",
                temporary_name,
                "-p",
                f"127.0.0.1:{args.temporary_port}:8000",
                "-e",
                "OLLAMA_BASE_URL=http://127.0.0.1:1",
                "backend",
            ],
            "unavailable-model-container",
        )
        temporary_started = True
        alternate = f"http://127.0.0.1:{args.temporary_port}"
        wait_ready(alternate)
        fallback = request(
            alternate,
            "/query",
            {
                "question": "Is Orchid production launch approved and when is the next review?",
                "source_file": pdf,
            },
            "POST",
        )
        assert (
            isinstance(fallback, dict)
            and fallback["status"] == "evidence_only"
            and fallback["model"] is None
        )
        assert (
            "not approved" in fallback["answer"] and "2026-11-03" in fallback["answer"]
        )
        record("unavailable-model-honest-fallback", fallback)
        command(["docker", "stop", temporary_name], "stop-temporary")
        command(["docker", "rm", temporary_name], "remove-temporary")
        temporary_started = False
        command(compose + ["start", "backend"], "restart-main")
        main_stopped = False
        wait_ready(args.base_url)
        catalog = request(args.base_url, "/documents")
        assert isinstance(catalog, list)
        for item in catalog:
            if item["source_file"] not in {sales, pdf}:
                raise RuntimeError("Unexpected document appeared; cleanup stopped")
            from urllib.parse import quote

            request(
                args.base_url,
                "/documents/"
                + quote(item["source_file"])
                + "?document_id="
                + quote(item["document_id"]),
                method="DELETE",
            )
        assert request(args.base_url, "/documents") == []
        record("selective-cleanup", {"catalog_empty": True})
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = type(exc).__name__ + ": " + str(exc)
        print(report["error"])
    finally:
        if restore_started:
            subprocess.run(
                ["docker", "rm", "-f", restore_name], cwd=ROOT, capture_output=True
            )
        if temporary_started:
            subprocess.run(
                ["docker", "rm", "-f", temporary_name], cwd=ROOT, capture_output=True
            )
        if main_stopped:
            result = subprocess.run(
                compose + ["start", "backend"], cwd=ROOT, capture_output=True
            )
            report["main_restart_returncode"] = result.returncode
        (out / "summary.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
        archive = out.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
            for p in out.rglob("*"):
                if p.is_file() and "backup" not in p.relative_to(out).parts:
                    z.write(p, p.relative_to(out))
        print("REPORT ZIP: " + str(archive))
    return int(report["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
