"""Validate curated UI images or promote explicitly reviewed live captures.

Raw capture reports stay local. This tool never calls the application, stages
files, commits, uploads, or pushes. Existing gallery files are backed up before
an explicitly requested promotion.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path("docs/assets/screenshots")
DEFINITIONS = {
    "lookup": (
        "UI-01",
        "Desktop lookup with original-cell evidence expanded",
        "North revenue of 45,000 with Q3 Sales row 2 and original cell B2.",
        "desktop-lookup.png",
    ),
    "subtotal": (
        "UI-02",
        "Available-value subtotal with the missing source cell disclosed",
        "Hours subtotal of 15.75 with missing B4 excluded and recorded zero retained.",
        "desktop-subtotal.png",
    ),
    "actual-model-narrative": (
        "UI-03",
        "Local-model narrative answer with source evidence",
        "Orchid launch is not approved; the next review is 2026-11-03.",
        "desktop-narrative.png",
    ),
    "unknown-subject": (
        "UI-04",
        "No matching evidence for an absent subject",
        "Rose has no matching evidence; Orchid facts are not substituted.",
        "desktop-no-evidence.png",
    ),
}


def png_info(path: Path) -> dict:
    """Read dimensions and a digest without editing the original capture."""
    if path.stat().st_size > 25 * 1024 * 1024:
        raise ValueError("Screenshot exceeds the 25 MiB gallery budget")
    raw = path.read_bytes()
    if len(raw) < 33 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        raise ValueError("Expected a PNG capture: " + path.name)
    width, height = struct.unpack(">II", raw[16:24])
    if not 1 <= width <= 16384 or not 1 <= height <= 32768:
        raise ValueError("Invalid screenshot dimensions: " + path.name)
    offset = 8
    chunk_types = []
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset : offset + 4])[0]
        boundary = offset + 12 + length
        if boundary > len(raw):
            raise ValueError("Truncated PNG capture")
        kind = raw[offset + 4 : offset + 8]
        data = raw[offset + 8 : offset + 8 + length]
        crc = struct.unpack(">I", raw[offset + 8 + length : boundary])[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != crc:
            raise ValueError("PNG chunk checksum failed")
        chunk_types.append(kind)
        offset = boundary
        if kind == b"IEND":
            break
    if (
        offset != len(raw)
        or chunk_types[-1:] != [b"IEND"]
        or b"IDAT" not in chunk_types
    ):
        raise ValueError("Incomplete PNG capture")
    return {"width": width, "height": height, "sha256": hashlib.sha256(raw).hexdigest()}


def render_gallery(manifest: dict) -> str:
    """Render references only for images in the approved gallery manifest."""
    text = """# Document Desk MVP — application walkthrough

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## What the desktop workspace looks like

Choose a document in the library, ask a question in the main panel, then open the answer's source evidence. The images below are real application captures with synthetic documents. Their captions identify controlled versus actual-model execution; they are not universal accuracy or performance claims.

"""
    for item in manifest["screenshots"]:
        identifier, title, description, _ = DEFINITIONS[item["scenario"]]
        text += (
            "**Figure "
            + identifier
            + " — "
            + title
            + ".**\n\n"
            + "!["
            + description
            + "](assets/screenshots/"
            + item["file"]
            + ")\n\n"
            + description
            + " **Capture mode:** "
            + item["mode"]
            + ". Application "
            + item["application_version"]
            + "; captured width "
            + str(item["width"])
            + " pixels. Images are unmodified.\n\n"
        )
    text += """## Read the answer and inspect its source

- The answer appears before detailed evidence. Status distinguishes answered, incomplete, no matching evidence and clarification.
- Open a source citation to inspect its row, cell or PDF location. Focus outlines can appear in keyboard-navigation captures.
- A subtotal warning identifies the missing source cells. It must remain visible with the result.
- **New chat** clears the conversation while keeping documents. **Remove** affects one selected document. **Reset workspace** is a separate confirmed action.

## Reproduce the screens

Use [native setup](setup.md) or [Docker deployment](docker.md), then follow the [browser smoke test](setup.md#8-verify-the-application-in-the-browser). For automated screenshots, use [the capture guide](screenshots.md). Raw captures stay in ignored reports; only reviewed images are copied into this gallery.

A caption marked **controlled browser capture** means the real UI/API/source records were exercised with explicit embedding/vector/model test adapters. It is not actual-model throughput evidence. An **actual-model application capture** uses the ordinary local services; structured calculations still do not call the model. Real-model behavior has its own [verification scope](validation.md).

## Maintain the gallery

The [gallery manifest](assets/screenshots/gallery.json) records image mode, dimensions and hashes without raw questions/responses or machine paths. Run:

"""
    fence = chr(96) * 3
    return (
        text
        + fence
        + "powershell\npython .\\tools\\ui_gallery.py --check\n"
        + fence
        + "\n\nReview the images as well as the checks. A file hash proves identity, not content correctness or permission to publish.\n"
    )


def check(root: Path = ROOT) -> list[str]:
    """Check exact assets and page references; never rewrite on --check."""
    problems = []
    try:
        manifest = json.loads(
            (root / ASSETS / "gallery.json").read_text(encoding="utf-8")
        )
        items = manifest["screenshots"]
        if not isinstance(items, list) or not items:
            raise ValueError("No curated images")
        seen = set()
        for item in items:
            scenario = item["scenario"]
            if scenario not in DEFINITIONS or scenario in seen:
                raise ValueError("Unknown or duplicate gallery scenario")
            seen.add(scenario)
            expected_name = DEFINITIONS[scenario][3]
            if item["file"] != expected_name:
                raise ValueError("Unexpected gallery filename")
            info = png_info(root / ASSETS / expected_name)
            if any(item.get(k) != v for k, v in info.items()):
                problems.append("Image identity/dimensions differ: " + expected_name)
            if item["mode"] not in {
                "controlled browser capture",
                "actual-model application capture",
            }:
                raise ValueError("Unknown execution mode")
            if item["application_version"] != "0.3.8":
                raise ValueError("Unexpected application version")
        if (root / "docs/ui.md").read_text(encoding="utf-8") != render_gallery(
            manifest
        ):
            problems.append("UI walkthrough differs from its curated manifest")
        actual = {p.name for p in (root / ASSETS).glob("*.png")}
        if actual != {item["file"] for item in items}:
            problems.append("Unregistered or missing gallery PNG")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        problems.append("Invalid gallery: " + str(exc))
    return problems


def plan_promotion(folder: Path, scenarios: list[str], reviewed: bool) -> list[tuple]:
    """Validate every selected capture before allowing any source-file writes."""
    if not reviewed:
        raise ValueError("Inspect the captures, then explicitly pass --reviewed")
    if not scenarios or len(set(scenarios)) != len(scenarios):
        raise ValueError("Select unique capture scenarios")
    folder = folder.resolve(strict=True)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("application_version") != "0.3.8"
        or manifest.get("operator_mode") != "actual_model_required_for_narrative"
    ):
        raise ValueError("Use a capture:live manifest for application 0.3.8")
    entries = manifest.get("captures")
    if not isinstance(entries, list):
        raise ValueError("Missing capture entries")
    if manifest.get("viewport", {}).get("width") not in {1280, 1440, 1920}:
        raise ValueError("Use a documented desktop capture width")
    planned = []
    for scenario in scenarios:
        matches = [c for c in entries if c.get("scenario") == scenario]
        if scenario not in DEFINITIONS or len(matches) != 1:
            raise ValueError("Unknown or ambiguous capture scenario: " + scenario)
        entry = matches[0]
        if (
            entry.get("status") != "passed"
            or entry.get("validation_status") != "passed"
        ):
            raise ValueError("Selected capture did not pass: " + scenario)
        filename = entry.get("file")
        if not isinstance(filename, str) or not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.-]*\.png", filename
        ):
            raise ValueError("Capture file must be a local PNG basename")
        image = folder / filename
        if image.is_symlink() or image.resolve().parent != folder:
            raise ValueError("Capture path escapes the selected run")
        info = png_info(image)
        if info["width"] != manifest.get("viewport", {}).get("width"):
            raise ValueError("Capture width differs from its manifest")
        planned.append((scenario, image, info))
    return planned


def promote(
    folder: Path, scenarios: list[str], reviewed: bool, root: Path = ROOT
) -> Path:
    """Promote selected captures, with local backup and rollback on write failure."""
    planned = plan_promotion(folder, scenarios, reviewed)
    if check(root):
        raise ValueError("Current gallery failed checks; preserve it before promotion")
    asset_dir = root / ASSETS
    manifest_path = asset_dir / "gallery.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    replacements = {s: (image, info) for s, image, info in planned}
    current = {item["scenario"]: item for item in manifest["screenshots"]}
    for scenario, (_, info) in replacements.items():
        current[scenario] = {
            "scenario": scenario,
            "file": DEFINITIONS[scenario][3],
            "application_version": "0.3.8",
            "mode": "actual-model application capture",
            **info,
        }
    manifest["screenshots"] = [current[s] for s in DEFINITIONS if s in current]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = root / "reports/ui-gallery-backups" / stamp
    backup.mkdir(parents=True)
    targets = [root / "docs/ui.md", manifest_path] + [
        asset_dir / DEFINITIONS[s][3] for s in replacements
    ]
    originals = {p: p.read_bytes() if p.exists() else None for p in targets}
    for index, (p, content) in enumerate(originals.items()):
        if content is not None:
            (backup / f"{index}-{p.name}").write_bytes(content)
    try:
        for scenario, (image, _) in replacements.items():
            shutil.copyfile(image, asset_dir / DEFINITIONS[scenario][3])
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        (root / "docs/ui.md").write_text(render_gallery(manifest), encoding="utf-8")
        problems = check(root)
        if problems:
            raise ValueError("; ".join(problems))
    except Exception:
        for p, content in originals.items():
            if content is None:
                p.unlink(missing_ok=True)
            else:
                p.write_bytes(content)
        raise
    return backup


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--from-run", type=Path)
    parser.add_argument("--scenarios", nargs="+", choices=list(DEFINITIONS))
    parser.add_argument("--reviewed", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            issues = check()
            for issue in issues:
                print(issue)
            print("UI gallery: " + ("FAILED" if issues else "PASSED"))
            return int(bool(issues))
        backup = promote(args.from_run, args.scenarios or [], args.reviewed)
        print("REPLACED IMAGE BACKUP:", backup)
        print("Gallery updated locally. Nothing staged, uploaded or pushed.")
        print("Run python tools/catalog.py after adding new gallery images.")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print("UI gallery stopped:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
