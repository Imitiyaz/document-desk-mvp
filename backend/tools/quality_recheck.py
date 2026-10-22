"""Run source-record acceptance cases against a fresh API index; save full evidence.

Usage from project root: python backend/tools/quality_recheck.py --base-url http://127.0.0.1:8000
This uploads only bundled fixtures. It never replaces documents or deletes an index.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and release tooling
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "backend/tests/fixtures/quality/cases.json"


def validate_case(case: dict[str, Any], body: dict[str, Any]) -> list[str]:
    """Compare exact source identities, cell values, labels, citations and results.

    No substring number test can establish a pass here. Reference cases are
    independently reviewed source facts. Human review remains useful for broader
    documents beyond this explicitly bounded fixture corpus.
    """
    from tools.presentation_checks import readable_findings

    expected = case["expected"]
    if (
        not isinstance(body, dict)
        or not isinstance(body.get("records"), list)
        or not isinstance(body.get("citations"), list)
    ):
        return ["Response does not have the required record/citation shape"]
    if any(
        not isinstance(r, dict) or not isinstance(r.get("values"), dict)
        for r in body["records"]
    ):
        return ["Malformed source record"]
    if any(not isinstance(c, dict) for c in body["citations"]):
        return ["Malformed source citation"]
    findings = []
    if body.get("status") != expected["status"]:
        findings.append(
            f"Answer status: expected {expected['status']}, got {body.get('status')}"
        )
    actual = body.get("records", [])
    if "continuations" in expected:
        for record in actual:
            wanted_continuation = expected["continuations"].get(
                str(record.get("number")), {}
            )
            if record.get("continuation_fields", {}) != wanted_continuation:
                findings.append(
                    "Original blank/continuation anchor provenance does not match the source contract"
                )
    wanted = expected["records"]
    if len(actual) != len(wanted):
        findings.append(
            f"Source coverage: expected {len(wanted)} records, got {len(actual)}"
        )
    for index, (sheet, row, field, value) in enumerate(wanted):
        if index >= len(actual):
            continue
        record = actual[index]
        if (
            record.get("source_file"),
            record.get("sheet_or_page"),
            record.get("row_or_location"),
        ) != (case["request"]["source_file"], sheet, row):
            findings.append(f"Record {index+1}: wrong source identity/order")
        if field not in record.get("values", {}) or record["values"][field] != value:
            findings.append(f"Record {index+1}: wrong/missing {field} value")
    if (
        "labels" in expected
        and [r.get("values", {}).get("Region") for r in actual] != expected["labels"]
    ):
        findings.append("Ordinary blank/entity labels do not match original cells")
    calculation = body.get("calculation")
    if (calculation.get("result") if calculation else None) != expected["result"]:
        findings.append("Computed result does not match the independent exact oracle")
    if expected["result"] is None and calculation is not None:
        findings.append("Unrequested or unsupported calculation was returned")
    if expected["result"] is not None and calculation:
        text = " ".join(
            str(body.get("evidence_text") or body.get("answer", "")).split()
        )
        op = calculation.get("operation")
        for field, value in expected["result"].items():
            if op == "sum":
                required = f"{field} = {value}"
            elif op in {"minimum", "maximum"}:
                required = f"{op} {field}: {value}"
            else:
                required = f"{value} (Source: [{field}])"
            ending = r"(?=\s*(?:;|$))" if op in {"sum", "minimum", "maximum"} else ""
            if re.search(re.escape(required) + ending, text) is None:
                findings.append(
                    "Displayed calculation disagrees with its exact result/source mapping"
                )
        operands = calculation.get("operands", [])
        if expected.get("partial"):
            wanted_numbers = [
                r["number"]
                for r, (_, _, _, value) in zip(actual, wanted, strict=False)
                if value is not None
            ]
            if [o.get("number") for o in operands] != wanted_numbers:
                findings.append(
                    "Subtotal omitted/added/imputed a contributing source record"
                )
            excluded = calculation.get("excluded_cells", [])
            if [
                {k: c.get(k) for k in ("number", "field", "cell")} for c in excluded
            ] != expected["excluded_cells"] or calculation.get("partial") is not True:
                findings.append("Subtotal exclusions/completeness are incorrect")
            included_records = [r for r in actual if r["number"] in wanted_numbers]
        else:
            if len(operands) != len(wanted):
                findings.append("Calculation operand coverage is incomplete")
            included_records = actual
        for record, operand in zip(included_records, operands, strict=False):
            if operand.get("number") != record.get("number"):
                findings.append("Calculation operand refers to the wrong source record")
    # Validate each displayed record span, so a value elsewhere in the answer
    # cannot hide a wrong entity/value/citation pairing on this record.
    flat_text = " ".join(
        str(body.get("evidence_text") or body.get("answer", "")).split()
    )
    previous_end = 0
    for record in actual:
        marker = re.search(
            r"\(Source: \[" + str(record.get("number")) + r"\]\)",
            flat_text[previous_end:],
        )
        if marker is None:
            findings.append("Displayed record lacks its source reference")
            continue
        segment = flat_text[previous_end : previous_end + marker.start()]
        previous_end += marker.end()
        values_text = "; ".join(
            f"{field}: {value if value is not None else 'Missing in source'}"
            for field, value in record["values"].items()
        )
        location = f"{record['source_file']} / {record['sheet_or_page']} / row {record['row_or_location']}"
        expected_display = f"- {location} — {values_text}".replace("[", "［").replace(
            "]", "］"
        )
        prefix = " ".join(
            f"- {location} —".replace("[", "［").replace("]", "］").split()
        )
        start = segment.find(prefix)
        shown_record = segment[start:].strip() if start >= 0 else ""
        if " ".join(expected_display.split()) != shown_record:
            findings.append(
                "Displayed record has a missing or misassociated source/value"
            )
    citations = body.get("citations", [])
    if len(citations) != len(wanted):
        findings.append("Separate source references were omitted or added")
    for record in actual:
        matches = [c for c in citations if c.get("number") == record.get("number")]
        if len(matches) != 1 or any(
            matches[0].get(k) != record.get(k)
            for k in ("source_file", "sheet_or_page", "row_or_location")
        ):
            findings.append("Claim-to-record citation mapping is inconsistent")
    if wanted and body.get("coverage", {}).get("returned_records") != len(wanted):
        findings.append("Coverage count does not match the required source set")
    if body.get("unresolved_citation_numbers"):
        findings.append("Unresolved citations")
    if body.get("execution_path") != "structured" or body.get("model") is not None:
        findings.append("Table answer unexpectedly used unconstrained model generation")
    findings.extend(readable_findings(body))
    return sorted(set(findings))


def run(base_url: str, output: Path) -> int:
    """Upload fixtures once and run every independent acceptance case."""
    opener = build_opener(ProxyHandler({}))
    report: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "api_version_expected": ["0.3.5", "0.3.6", "0.3.7", "0.3.8"],
        "cases": [],
        "uploads": [],
        "method": "actual HTTP; source-record and arithmetic oracle; full responses retained",
    }
    durations = []

    def call(
        path: str, data: bytes | None = None, content_type: str | None = None
    ) -> tuple[int, Any]:
        request = Request(
            base_url.rstrip("/") + path,
            data=data,
            headers={"Content-Type": content_type} if content_type else {},
        )
        try:
            response = opener.open(request, timeout=180)
        except HTTPError as exc:
            response = exc
        with response:
            return response.code, json.loads(response.read())

    try:
        status, schema = call("/openapi.json")
        if status != 200 or schema.get("info", {}).get("version") not in {
            "0.3.5",
            "0.3.6",
            "0.3.7",
            "0.3.8",
        }:
            raise ValueError(
                "Start the updated API 0.3.5, 0.3.6, 0.3.7 or 0.3.8 before running this check."
            )
        cases = json.loads(CASES.read_text(encoding="utf-8-sig"))["cases"]
        for filename in sorted({c["request"]["source_file"] for c in cases}):
            boundary = "quality-" + uuid4().hex
            content = (ROOT / "backend/tests/fixtures" / filename).read_bytes()
            data = (
                f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()
                + content
                + f"\r\n--{boundary}--\r\n".encode()
            )
            status, body = call(
                "/documents", data, f"multipart/form-data; boundary={boundary}"
            )
            report["uploads"].append(
                {"source_file": filename, "http_status": status, "body": body}
            )
            if status != 201:
                raise ValueError(
                    f"{filename}: expected upload201, got {status}. Use a fresh index; no data was replaced."
                )
        for case in cases:
            started = time.perf_counter()
            status, body = call(
                "/query", json.dumps(case["request"]).encode(), "application/json"
            )
            elapsed = time.perf_counter() - started
            durations.append(elapsed)
            findings = (
                validate_case(case, body)
                if status == 200
                else [f"Expected HTTP200, got {status}"]
            )
            report["cases"].append(
                {
                    "id": case["id"],
                    "request": case["request"],
                    "http_status": status,
                    "body": body,
                    "elapsed_seconds": elapsed,
                    "findings": findings,
                }
            )
            print(
                f"{case['id']}: HTTP {status}; {'PASS' if not findings else '; '.join(findings)}",
                flush=True,
            )
        report["checks_with_findings"] = sum(
            bool(c["findings"]) for c in report["cases"]
        )
        report["query_timing_seconds"] = {
            "median": statistics.median(durations),
            "maximum": max(durations),
            "count": len(durations),
        }
    except (OSError, ValueError) as exc:
        report["runner_error"] = str(exc)
        report["checks_with_findings"] = 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {output}")
    return 1 if report.get("checks_with_findings") else 0


def main() -> int:
    """CLI entrypoint with explicit local base URL and report location."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "reports/quality"
        / f"quality-{datetime.now(UTC):%Y%m%dT%H%M%SZ}.json",
    )
    args = parser.parse_args()
    return run(args.base_url, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
