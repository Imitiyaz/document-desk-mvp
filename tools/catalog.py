"""Generate categorized, exhaustive source-file navigation from the shipped tree.

Generated catalogs are public developer documentation. Runtime data, caches and
private review materials are intentionally outside the source inventory.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
from pathlib import Path


def attribution(relative):
    """Credit human authorship and AI assistance on generated navigation."""
    depth = len(Path(relative).parts) - 1
    target = "../" * depth + "AUTHORS.md"
    return (
        "Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution]("
        + target
        + ").\n\n"
    )


ROOT = Path(__file__).resolve().parents[1]
SKIP = {
    ".git",
    ".venv",
    ".test-venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "coverage",
    "htmlcov",
    "reports",
    "test-results",
    "playwright-report",
    "data",
    "private",
    "local",
}
GROUPS = {
    "project": "Project, licensing and repository configuration",
    "backend": "Backend application and contracts",
    "backend-tests": "Backend tests, synthetic fixtures and independent oracles",
    "backend-tooling": "Backend dependencies and verification utilities",
    "frontend": "Frontend application, styles and component tests",
    "frontend-tests": "Browser workflows and answer comparison tools",
    "frontend-delivery": "Frontend build, legal assets and configuration",
    "documentation": "Documentation, decisions and navigation",
    "delivery": "Deployment, repository checks and release tooling",
}


def paths(root: Path) -> list[Path]:
    result = []
    for current, directories, files in os.walk(root):
        directories[:] = [
            d
            for d in directories
            if d not in SKIP and not d.startswith(("pytest-of-", "test-results-prior-"))
        ]
        for name in files:
            p = Path(current) / name
            if (
                name.endswith((".pyc", ".log", ".tsbuildinfo", ".zip"))
                or name.startswith((".coverage", ".env."))
                and name != ".env.example"
                or name == ".env"
            ):
                continue
            result.append(p)
    # Path ordering follows the host OS: Windows folds case, whereas POSIX
    # preserves it. Sort relative path components as strings so a checked-in
    # catalog has the same order on both platforms, including mixed-case names.
    return sorted(result, key=lambda path: path.relative_to(root).parts)


def category(path: str) -> str:
    if path.startswith("backend/app/"):
        return "backend"
    if path.startswith("backend/tests/"):
        return "backend-tests"
    if path.startswith("backend/"):
        return "backend-tooling"
    if path.startswith("frontend/src/"):
        return "frontend"
    if path.startswith(("frontend/e2e/", "frontend/tools/")):
        return "frontend-tests"
    if path.startswith("frontend/"):
        return "frontend-delivery"
    if path.startswith("docs/"):
        return "documentation"
    if path.startswith(("tools/", "deploy/")):
        return "delivery"
    return "project"


def purpose(path: Path) -> str:
    name = path.name
    if path.suffix == ".md":
        text = path.read_text(encoding="utf-8")
        match = re.search(r"^# (.+)$", text, re.M)
        if match:
            return match.group(1).strip()
    if path.suffix == ".py":
        try:
            doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8-sig")))
            if doc:
                return re.split(r"\s+Author:", " ".join(doc.splitlines()[0:1]))[
                    0
                ].strip()
        except (SyntaxError, UnicodeError):
            pass
        if name == "__init__.py":
            return (
                "Python package boundary and explicit public imports for "
                + path.parent.name
            )
    if path.suffix in {".ts", ".tsx", ".mjs", ".js", ".css"}:
        text = path.read_text(encoding="utf-8")
        match = re.search(r"/\*\*(.*?)\*/", text, re.S)
        if match:
            lines = [
                re.sub(r"^\s*\*?\s*", "", line).strip()
                for line in match.group(1).splitlines()
            ]
            description = next((line for line in lines if line), "")
            if description:
                return re.split(r"\s+Author:", description)[0].rstrip(".")
        if name.endswith((".test.tsx", ".test.mjs")):
            return "Regression tests for " + name.split(".test")[0]
    exact = {
        "dependabot.yml": "Scheduled dependency-update pull requests for pip, npm and GitHub Actions; no automatic merge",
        "extensions.json": "Recommended editor extensions for Python, React/TypeScript, linting and formatting",
        "settings.json": "Portable VS Code interpreter, test, analysis and formatting configuration",
        "prompt_eval_questions.json": "Synthetic question/reference cases for bounded prompt and model diagnostic evaluation",
        "cases.json": "Independent quality case definitions and expected source/value requirements",
        "diagram-register.json": "Stable figure IDs and authoritative documentation locations for the README visual tour and diagram index",
        "gallery.json": "Curated UI image modes, dimensions and identity hashes; excludes raw capture reports",
        "desktop-lookup.png": "Unmodified controlled desktop capture showing North 45000 and Q3 Sales B2 evidence",
        "desktop-subtotal.png": "Unmodified controlled desktop capture showing the Hours subtotal and missing B4 warning",
        "desktop-narrative.png": "Reviewed ordinary-application capture of the local-model narrative scenario",
        "desktop-no-evidence.png": "Reviewed ordinary-application capture showing no evidence for an absent subject",
        "RAG_MVP.postman_collection.json": "Portable API upload/query/conversation examples with local variables and no credentials",
        "LICENSE": "Complete GNU AGPL version 3 license text for the original application",
        ".env.example": "Non-secret example environment variables; copy locally, never commit real credentials",
        ".gitignore": "Exclude environments, indexes, credentials, private notes and generated reports",
        ".dockerignore": "Exclude private data, caches and development outputs from image build contexts",
        ".gitattributes": "Repository text/binary and line-ending policy",
        ".pre-commit-config.yaml": "Optional local quality hooks aligned with the project tools",
        "compose.yaml": "Local two-service deployment, host Ollama connection and named persistence volumes",
        "nginx.conf": "Static frontend, internal API proxy, health endpoint and response headers",
        "Dockerfile": "Container image build and runtime entrypoint for "
        + path.parent.name,
        "package-lock.json": "Locked frontend dependency graph; used by npm ci",
        "package.json": "Frontend dependency versions, scripts, runtime range and license metadata",
        "pytest.ini": "Test collection defaults and explicit slow/native/model markers",
        "pyproject.toml": "Backend formatter/linter configuration",
        "requirements.txt": "Direct full-runtime dependency pins and core dependency include",
        "requirements-core.txt": "Core API/document parsing dependency pins without model/vector runtimes",
        "requirements-dev.txt": "Full runtime plus developer/test tools",
        "requirements-test.txt": "Lightweight isolated test/quality/fixture dependencies",
        "openapi.json": "Exported API schema for the application version; compare with running /openapi.json",
        "source-info.json": "Source-release/license status; operator must configure exact source availability before shared hosting",
        "legal.html": "Browser-visible license, source availability and model attribution page",
        "license.txt": "Exact AGPL license copy served by the frontend",
        "files.json": "Machine-readable exhaustive public file inventory and purpose/category map",
        "release.json": "Public application/source revision, license and local deployment facts",
        "ci.yml": "Read-only repository/backend/frontend/browser CI; no automatic publication",
        "source-data.json": "Independent synthetic acceptance facts for PDF/Excel fixtures",
        "index.html": "Frontend HTML entrypoint and mounting element",
    }
    if name in exact:
        return exact[name]
    if path.suffix in {".xlsx", ".pdf"}:
        return (
            "Synthetic "
            + ("workbook" if path.suffix == ".xlsx" else "PDF")
            + " fixture: "
            + path.stem.replace("_", " ").replace("-", " ")
            + "; test data, not a user document"
        )
    if name.startswith("tsconfig"):
        return "TypeScript compiler scope and strictness: " + name
    if path.suffix == ".json":
        return (
            "Structured "
            + path.stem.replace("-", " ")
            + " configuration or test facts; see the referencing source/tests"
        )
    return (
        "Project "
        + path.parent.name
        + " "
        + name.replace("_", " ")
        + "; explicit source/configuration input"
    )


def render(root: Path) -> dict[str, str]:
    listing = paths(root)
    entries = [
        {
            "path": p.relative_to(root).as_posix(),
            "category": category(p.relative_to(root).as_posix()),
            "purpose": purpose(p),
        }
        for p in listing
    ]
    output = {
        "docs/catalog/files.json": json.dumps(
            {
                "schema_version": 1,
                "scope": "all_shipped_source_files_excludes_runtime_private_and_generated_results",
                "files": entries,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n"
    }
    group_links = []
    for i, (group, title) in enumerate(GROUPS.items(), 1):
        rows = [e for e in entries if e["category"] == group]
        text = f"# {title}\n\nGenerated by [catalog.py](../../tools/catalog.py). Every entry links to the actual file; descriptions explain its role. See the [project map](../../PROJECT_MAP.md) and [catalog index](index.md).\n\n**Table CAT-{i:02d} — {title}.**\n\n| File | Purpose |\n| --- | --- |\n"
        for e in rows:
            text += (
                "| ["
                + e["path"]
                + "](../../"
                + e["path"]
                + ") | "
                + e["purpose"].replace("|", " / ").replace("\n", " ")
                + " |\n"
            )
        output["docs/catalog/" + group + ".md"] = text
        group_links.append(f"| [{title}]({group}.md) | {len(rows)} |")
    output["docs/catalog/index.md"] = (
        "# Complete source-file catalog\n\nEvery shipped file appears exactly once in a category and in [files.json](files.json). Generated reports, environments, user documents, indexes and private review notes are excluded from the source package. No ordinary application file is intentionally undocumented.\n\n**Table CAT-00 — Catalog categories and file counts.**\n\n| Category | Files |\n| --- | --- |\n"
        + "\n".join(group_links)
        + "\n\nRegenerate with `python tools/catalog.py`; check drift with `python tools/catalog.py --check`. Descriptions summarize purpose, not every function contract. Implementation details remain in source comments/docstrings and linked design documentation.\n"
    )
    output["PROJECT_MAP.md"] = (
        "# Project map — find documentation and every source file\n\nStart with [README](README.md) for product scope, [documentation index](docs/index.md) for guides and [complete file catalog](docs/catalog/index.md) for every shipped file. The inventory currently covers **"
        + str(len(entries))
        + " files**. Runtime/private material is excluded by design.\n\n**Table MAP-01 — Project areas and navigation.**\n\n| Area | Purpose and reference |\n| --- | --- |\n"
        + "\n".join(
            "| " + title + " | [File-by-file catalog](docs/catalog/" + group + ".md) |"
            for group, title in GROUPS.items()
        )
        + "\n\nThis map is generated from the source tree. Check it in CI instead of manually adding unverified file counts. See [README visual tour and diagram index](docs/diagrams.md), [technology stack](docs/technology-stack.md) and [acceptance boundaries](docs/acceptance.md).\n"
    )
    docs = [e for e in entries if e["path"].endswith(".md")]
    text = "# Documentation index — guides, decisions and all Markdown files\n\nUse the [project map](../PROJECT_MAP.md) to browse every source file. This index covers every shipped Markdown document, including templates, fixture notes and the generated category pages. The [README visual tour and diagram index](diagrams.md) collects all figures with links to their authoritative explanations.\n\n## Read by task\n\n- Install and verify: [native setup without Docker](setup.md), [Docker deployment](docker.md), [usage](usage.md), [troubleshooting](troubleshooting.md).\n- Understand: [stack and rationale](technology-stack.md), [architecture](../ARCHITECTURE.md), [browser-to-answer journey](journey.md), [pipeline](pipeline.md), [data model](data-model.md), [API](api.md).\n- Develop and verify: [development](development.md), [testing](testing.md), [UI walkthrough](ui.md), [screenshots](screenshots.md), [validation](validation.md).\n- Operate and assess: [operations and recovery](operations.md), [targeted cleanup](cleanup.md), [data locality](privacy.md), [security](../SECURITY.md), [limitations](limitations.md), [acceptance](acceptance.md), [license](../LICENSE-NOTICE.md).\n\n## Design decisions\n\nDecisions record context, implemented choice, rationale, consequences, verification and reconsideration triggers. They do not approve future dependency changes.\n\n"
    for label, subset in [
        (
            "Guides and root documents",
            [
                e
                for e in docs
                if "/decisions/" not in e["path"] and "/catalog/" not in e["path"]
            ],
        ),
        ("Decision records", [e for e in docs if "/decisions/" in e["path"]]),
        ("File catalogs", [e for e in docs if "/catalog/" in e["path"]]),
    ]:
        text += (
            "## "
            + label
            + "\n\n**Table IDX-"
            + str(
                [
                    "Guides and root documents",
                    "Decision records",
                    "File catalogs",
                ].index(label)
                + 1
            ).zfill(2)
            + " — "
            + label
            + ".**\n\n| Document | Purpose |\n| --- | --- |\n"
        )
        for e in subset:
            target = os.path.relpath(root / e["path"], root / "docs").replace(
                os.sep, "/"
            )
            text += (
                "| ["
                + e["path"]
                + "]("
                + target
                + ") | "
                + e["purpose"].replace("|", " / ")
                + " |\n"
            )
        text += "\n"
    output["docs/index.md"] = text
    for relative, value in list(output.items()):
        if relative.endswith(".md"):
            title_end = value.index("\n") + 1
            output[relative] = (
                value[:title_end]
                + "\n"
                + attribution(relative)
                + value[title_end:].lstrip("\n")
            )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    # Ensure generated files exist before inventory; generation is idempotent.
    generated = [
        "PROJECT_MAP.md",
        "docs/index.md",
        "docs/catalog/index.md",
        "docs/catalog/files.json",
    ] + ["docs/catalog/" + g + ".md" for g in GROUPS]
    if not args.check:
        for rel in generated:
            p = ROOT / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                p.write_text("# " + Path(rel).stem + "\n", encoding="utf-8")
        # Titles in the Markdown index converge after their category pages exist.
        for _ in range(3):
            for rel, content in render(ROOT).items():
                (ROOT / rel).write_text(content, encoding="utf-8")
        print("Catalog generated; every shipped source file is indexed")
        return 0
    differences = [
        rel
        for rel, content in render(ROOT).items()
        if not (ROOT / rel).exists()
        or (ROOT / rel).read_text(encoding="utf-8") != content
    ]
    for rel in differences:
        print("Catalog drift: " + rel)
    print("Catalog coverage: " + ("FAILED" if differences else "PASSED"))
    return int(bool(differences))


if __name__ == "__main__":
    raise SystemExit(main())
