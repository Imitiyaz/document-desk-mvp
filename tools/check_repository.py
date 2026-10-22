"""Check source-distribution boundaries and local Markdown links.

Heuristic checks only: this is not a complete secret/license/security audit.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import re
import sys
import json
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKIP = {
    ".git",
    ".venv",
    ".test-venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "coverage",
    "htmlcov",
    "test-results",
    "playwright-report",
    "reports",
    "data",
}
TEXT = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
    ".ini",
    ".ts",
    ".tsx",
    ".mjs",
    ".css",
}
PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b"),
    re.compile(r"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(r"\bsk-proj-[A-Za-z0-9_-]{30,}\b"),
]
FORBIDDEN_PATHS = (
    "docs/stages/",
    "docs/releases/",
    "docs/guides/",
    "docs/learning/",
    "docs/quality/",
    "docs/acceptance/",
    "articles/",
    "private/",
    "local/",
)


def inspect_diagrams(root: Path) -> list[str]:
    """Check all README figures against their registered implementation context.

    Source contracts complement Mermaid engine/render inspection. Multi-line
    Markdown strings are accepted; conditions must remain visibly labeled.
    """
    findings = []
    register_file = root / "docs/diagram-register.json"
    try:
        register = json.loads(register_file.read_text(encoding="utf-8"))
        identifiers = [e["id"] for e in register]
        if len(identifiers) != len(set(identifiers)):
            findings.append("Duplicate diagram register ID")
    except (OSError, ValueError, KeyError, TypeError):
        return ["Invalid or missing diagram register"]
    figure = re.compile(
        r"\*\*Figure ([A-Z0-9-]+) — ([^\n]+)\*\*\n\n```mermaid\n(.*?)```", re.S
    )
    locations = {}
    gallery = {}
    for md in root.rglob("*.md"):
        relative = md.relative_to(root)
        if any(
            part in SKIP or part.startswith("test-results-prior-")
            for part in relative.parts
        ):
            continue
        name = relative.as_posix()
        text = md.read_text(encoding="utf-8")
        matches = list(figure.finditer(text))
        if len(re.findall(r"^```mermaid\s*$", text, re.M)) != len(matches):
            findings.append("Untitled or unregistered-format Mermaid diagram: " + name)
        for match in matches:
            identifier, title, body = match.groups()
            key = (name, identifier)
            if key in locations:
                findings.append("Duplicate figure ID: " + identifier + " in " + name)
            locations[key] = (title.rstrip("."), body)
            if name == "README.md":
                gallery[identifier] = (title.rstrip("."), body)
            kind = body.splitlines()[0]
            if kind.startswith("flowchart"):
                # Arrow text may span several physical lines inside a quoted
                # Markdown label, so line-by-line counting would invent failures.
                arrows = len(re.findall(r"-->", body))
                labels = re.findall(r'-->\|"([^"\x00]+?)"\|', body, re.S)
                if arrows != len(labels) or any(
                    not label.strip("` \n") for label in labels
                ):
                    findings.append(
                        "Unlabeled flow edge: " + identifier + " in " + name
                    )
                if re.search(r'\{\s*"[^"\n]{25,}"\s*\}', body):
                    findings.append(
                        "Unwrapped long decision: " + identifier + " in " + name
                    )
            elif kind.startswith("stateDiagram"):
                if any("-->" in line and ":" not in line for line in body.splitlines()):
                    findings.append(
                        "Unlabeled state transition: " + identifier + " in " + name
                    )
            elif kind == "sequenceDiagram":
                if any(
                    ";" in line
                    for line in body.splitlines()
                    if re.search(r"--?>>\w+:", line)
                ):
                    findings.append(
                        "Unsafe sequence separator: " + identifier + " in " + name
                    )
                if any(
                    re.search(r"--?>>", line) and ":" not in line
                    for line in body.splitlines()
                ):
                    findings.append(
                        "Unlabeled sequence message: " + identifier + " in " + name
                    )
    if set(identifiers) != set(gallery):
        findings.append("README does not cover every registered figure")
    for entry in register:
        identifier = entry["id"]
        source = locations.get((entry["source"], identifier))
        mirror = gallery.get(identifier)
        if source is None:
            findings.append("Missing context figure: " + identifier)
            continue
        if (
            source[0] != entry["title"]
            or not entry.get("kind")
            or not entry.get("anchor")
        ):
            findings.append("Diagram metadata differs from source: " + identifier)
        if source != mirror:
            findings.append("README figure differs from context: " + identifier)
    expected = {(e["source"], e["id"]) for e in register} | {
        ("README.md", e["id"]) for e in register
    }
    if set(locations) != expected:
        findings.append("Unregistered or missing figure location")
    return findings


def inspect_attribution(root: Path) -> list[str]:
    """Keep documentation ownership explicit while crediting AI assistance."""
    findings = []
    for path in root.rglob("*.md"):
        relative = path.relative_to(root)
        if any(part in SKIP for part in relative.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if relative.as_posix() == "AUTHORS.md":
            if "**Imitiyaz**" not in text or "AI Agent" not in text:
                findings.append("Missing human/AI attribution roles")
            continue
        if "Author: **Imitiyaz**. AI assistance: **AI Agent**." not in text:
            findings.append(
                "Missing explicit documentation authorship: " + relative.as_posix()
            )
        if (
            "decisions" in relative.parts
            and "Decision owner and approver: **Imitiyaz**." not in text
        ):
            findings.append("Missing human decision ownership: " + relative.as_posix())
    return findings


def inspect_table_captions(text: str, name: str) -> list[str]:
    """Require a descriptive reference caption immediately before Markdown tables."""
    visible = re.sub(r"```.*?```", "", text, flags=re.S).splitlines()
    findings = []
    prior = ""
    for index, line in enumerate(visible):
        if (
            line.startswith("|")
            and index + 1 < len(visible)
            and re.match(r"\|\s*:?-{3}", visible[index + 1])
        ):
            if not re.fullmatch(r"\*\*Table [A-Z0-9-]+ — .+\*\*", prior):
                findings.append(f"Missing descriptive table caption: {name}")
        if line.strip():
            prior = line.strip()
    return findings


def inspect_public_release(root: Path) -> list[str]:
    """Keep a first public release free of private revision and account history."""
    findings = []
    changelog = root / "CHANGELOG.md"
    if changelog.exists():
        text = changelog.read_text(encoding="utf-8")
        sections = re.findall(r"^## (.+)$", text, re.M)
        if len(sections) != 1 or "Initial public release" not in sections[0]:
            findings.append("Changelog must describe one initial public release")
    private_markers = (
        re.compile(r"\b\d+\.\d+\.\d+-public\.\d+\b"),
        re.compile(r"\b(?:baseline|regression|golden)-\d+\.\d+\.\d+"),
        re.compile(r"as you requested|based on your review comments"),
        re.compile(r"https://github\.com/[^/\s]+/[^/\s]*(?:personal|private)[^/\s]*"),
    )
    for path in root.rglob("*.md"):
        if any(part in SKIP for part in path.relative_to(root).parts):
            continue
        content = path.read_text(encoding="utf-8").lower()
        if any(marker.search(content) for marker in private_markers):
            findings.append(
                "Internal history or assistant-to-owner prose: "
                + path.relative_to(root).as_posix()
            )
    return findings


def inspect(root: Path) -> list[str]:
    findings: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(
            part in SKIP or part.startswith(("pytest-of-", "test-results-prior-"))
            for part in relative.parts
        ):
            continue
        if path.is_symlink():
            findings.append(f"Symlink needs explicit review: {relative.as_posix()}")
            continue
        if not path.is_file():
            continue
        name = relative.as_posix()
        if name.startswith(FORBIDDEN_PATHS) or path.name in {
            "SESSION_HANDOVER.md",
            "CLAUDE.md",
            "SKILLS.md",
            "prompt-for-this-mvp.md",
        }:
            findings.append(f"Non-public source path: {name}")
        if path.name.startswith(".env") and path.name != ".env.example":
            findings.append(f"Local configuration in source: {name}")
        if path.suffix.lower() in {
            ".pem",
            ".pfx",
            ".p12",
            ".key",
            ".sqlite",
            ".sqlite3",
            ".db",
            ".zip",
        }:
            findings.append(f"Private/runtime/archive file needs review: {name}")
        if path.suffix.lower() not in TEXT:
            continue
        raw = path.read_bytes()
        content = raw.decode("utf-8-sig")
        if b"\r\r\n" in raw:
            findings.append(f"Malformed line endings: {name}")
        if any(pattern.search(content) for pattern in PATTERNS):
            findings.append(f"Possible credential in {name}; value not printed")
        if path.suffix == ".md":
            findings.extend(inspect_table_captions(content, name))
            fences = re.findall(r"^```", content, re.MULTILINE)
            if len(fences) % 2:
                findings.append(f"Unbalanced Markdown fences: {name}")
            for target in re.findall(r"\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", content):
                if target.startswith(("http:", "https:", "mailto:", "#")):
                    continue
                local = unquote(target.split("#", 1)[0])
                if local and not (path.parent / local).exists():
                    findings.append(f"Broken local link in {name}: {target}")
    findings.extend(inspect_diagrams(root))
    findings.extend(inspect_attribution(root))
    findings.extend(inspect_public_release(root))
    return findings


def main() -> int:
    findings = inspect(ROOT)
    for finding in findings:
        print(finding, file=sys.stderr)
    print("Repository checks: " + ("FAILED" if findings else "PASSED"))
    return int(bool(findings))


if __name__ == "__main__":
    raise SystemExit(main())
