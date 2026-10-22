# SPDX-License-Identifier: AGPL-3.0-only
"""Plan supported table questions from complete physical source records.

Scope, field and filter decisions precede arithmetic. Ambiguous or unsupported
requests clarify instead of guessing business relationships. Decimal operations,
original cell references and explicit missing-value states travel together.
The match budget is a fail-closed guard, not a measured capacity promise.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Structured
"""

from __future__ import annotations

import re
from decimal import Context, Decimal, InvalidOperation
from typing import Any

from app.api.schemas import (
    CitationResponse,
    EvidenceRecord,
    QueryRequest,
    QueryResponse,
)
from app.generation.record_renderer import _natural_key
from app.models.extracted import SourceMetadata, format_citation
from app.structured.aggregation import sum_available
from app.structured.cross_scope import (
    IDENTITIES,
    PERIODS,
    combine_fields,
    compare_sources,
    measure_name,
    repeated_cells,
    source_unit,
    union_issue,
)
from app.structured.intent import SUM_WORDS, aliases, entity_clause, unmatched_terms
from app.structured.scopes import resolve_question_scope, scope_problem

MAX_ANSWER_RECORDS = 25000


def normalize(value: str) -> str:
    """Case-insensitive whole-token matching without substring identifier matches."""
    return " ".join(re.findall(r"[\w]+", value.casefold()))


def header_name(value: str) -> str:
    """Match camel-case/underscored headers without altering literal identifiers."""
    return normalize(re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value).replace("_", " "))


def contains(text: str, phrase: str) -> bool:
    """Match normalized phrases as whole tokens."""
    return f" {normalize(phrase)} " in f" {normalize(text)} "


def number(value: Any) -> tuple[Decimal, str] | None:
    """Parse finite plain/grouped decimals and explicit units; reject booleans/dates.

    Currency symbols/codes are retained as units, not silently converted.
    A percent remains a percentage-point numeric value with a '%' unit.
    """
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    match = re.fullmatch(
        r"(?P<prefix>[$€£¥]|[A-Z]{3}\s+)?\s*(?P<value>[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*(?P<suffix>%|[A-Za-z][A-Za-z0-9²³/·^.-]{0,15})?",
        text,
    )
    if not match or (match["prefix"] and match["suffix"]):
        return None
    try:
        decimal = Decimal(match["value"].replace(",", ""))
    except InvalidOperation:
        return None
    if (
        not decimal.is_finite()
        or abs(decimal.adjusted()) > 24
        or (
            isinstance(decimal.as_tuple().exponent, int)
            and int(decimal.as_tuple().exponent) < -12
        )
    ):
        return None
    return (
        decimal.copy_negate() if negative else decimal,
        (match["prefix"] or match["suffix"] or "").strip(),
    )


def cell_equal(value: Any, requested: str) -> bool:
    """Match explicit equality without conflating signs, units or missing cells."""
    if value is None:
        return False
    if isinstance(value, str):
        return " ".join(value.casefold().split()) == " ".join(
            requested.casefold().split()
        )
    actual_number, wanted_number = number(value), number(requested)
    if actual_number is not None or wanted_number is not None:
        return actual_number is not None and actual_number == wanted_number
    return " ".join(str(value).casefold().split()) == " ".join(
        requested.casefold().split()
    )


def display(value: Any) -> str:
    """Render a computed finite Decimal without binary float arithmetic."""
    if isinstance(value, Decimal):
        text = format(value, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return "0" if text == "-0" else text

    return str(value)


def clarify(message: str, **coverage: object) -> QueryResponse:
    """Return a visible non-answer instead of guessing a scope or operation."""
    return QueryResponse(
        status="clarification_required",
        execution_path="structured",
        answer=message,
        citations=[],
        unresolved_citation_numbers=[],
        context_count=0,
        model=None,
        generation_latency_seconds=0,
        coverage=coverage,
    )


def table_answer(
    request: QueryRequest, source: str, document: dict[str, Any]
) -> QueryResponse | None:
    """Plan and answer a bounded table request from all eligible source rows.


    Args:
        request: Validated question and optional explicit constraints.
        source: Filename used in record/citation provenance.
        document: Complete normalized ledger payload, including raw-cell metadata.

    Returns:
        A structured response, clarification/refusal, or None when this planner
        does not recognize a table question and the caller may use narrative evidence.

    The full accepted population supplies operands. Matching limits fail visibly;
    they never turn a truncated subset into a supposedly complete total.
    """
    request, _ = resolve_question_scope(request, document, whole_document=False)
    if problem := scope_problem(request, document):
        return clarify(problem)
    rows = document["rows"]
    headers = sorted({key for row in rows for key in row["values"]})
    if request.source_scopes:
        known = {r["sheet_or_page"] for r in rows} | {
            b["sheet_or_page"] for b in document["text_blocks"]
        }
        if set(request.source_scopes) - known:
            return clarify("One or more selected sources do not exist.")
        rows = [r for r in rows if r["sheet_or_page"] in request.source_scopes]
        headers = sorted({k for row in rows for k in row["values"]})
    if request.sheet_or_page:
        if not any(r["sheet_or_page"] == request.sheet_or_page for r in rows):
            if any(
                t["sheet_or_page"] == request.sheet_or_page
                for t in document["text_blocks"]
            ):
                return None
            return clarify(
                "The selected sheet/page has no extracted table rows. Choose a listed table scope."
            )
        rows = [r for r in rows if r["sheet_or_page"] == request.sheet_or_page]
        headers = sorted({key for row in rows for key in row["values"]})
    else:
        named = set()
        remaining = normalize(request.question)
        for scope in sorted(
            {r["sheet_or_page"] for r in rows},
            key=lambda text: len(normalize(text)),
            reverse=True,
        ):
            pattern = r"(?<!\w)" + re.escape(normalize(scope)) + r"(?!\w)"
            if re.search(pattern, remaining):
                named.add(scope)
                remaining = re.sub(pattern, " ", remaining)
        if named:
            rows = [r for r in rows if r["sheet_or_page"] in named]
            headers = sorted({key for row in rows for key in row["values"]})
    fields = list(dict.fromkeys(request.fields))
    if not fields:
        words = set(header_name(request.question).split())
        fields = [h for h in headers if set(header_name(h).split()) <= words]
        # A label column mentioned in 'North region' is a filter, not a metric.
        measured = [
            h
            for h in fields
            if (
                header_name(h) not in IDENTITIES | PERIODS
                and any(number(r["values"].get(h)) is not None for r in rows)
            )
            or any(t in normalize(h).split() for t in ("date", "status", "comment"))
        ]
        if measured:
            fields = measured
    if not fields:
        words = set(header_name(request.question).split())
        partial = [
            h
            for h in headers
            if set(header_name(h).split()) & words
            and (
                any(number(r["values"].get(h)) is not None for r in rows)
                or any(
                    w in header_name(h).split() for w in ["date", "status", "comment"]
                )
            )
            and header_name(h) not in IDENTITIES | PERIODS
        ]
        if len(partial) == 1:
            fields = partial
        elif partial:
            response = clarify(
                "Which measure or period do you mean?", available_fields=partial
            )
            response.clarification_options = [{"label": h, "field": h} for h in partial]
            return response
    if not fields:
        if request.operation != "auto" or request.fields or request.filters:
            return clarify("Select an exact field from the document schema.")
        return None
    if any(f not in headers for f in fields):
        return clarify("One or more selected fields do not exist in this scope.")
    operation_text = request.question
    for field in fields:
        operation_text = re.sub(re.escape(field), " ", operation_text, flags=re.I)
    if re.search(
        r"\b(average|mean|median|weighted|count|ratio|multiply|divide|convert|conversion|exchange rate|forecast|predict)\b|how many",
        operation_text,
        re.I,
    ):
        return clarify(
            "That operation is not supported. Show records or use compatible totals/minimum/maximum/two-period comparisons; no substitute calculation was performed."
        )
    requested_quarters = set(re.findall(r"\bq[1-4]\b", request.question.casefold()))
    supported_quarters = set(
        re.findall(
            r"\bq[1-4]\b",
            header_name(
                " ".join(
                    fields
                    + [r["sheet_or_page"] for r in rows]
                    + [
                        str(v)
                        for r in rows
                        for k, v in r["values"].items()
                        if header_name(k) in PERIODS
                    ]
                )
            ),
        )
    )
    if requested_quarters - supported_quarters:
        return clarify(
            "A requested quarter is absent from the selected scope; no period was silently ignored."
        )
    # Conservative unknown-clause handling: do not silently ignore unsupported predicates.
    if re.search(
        r"\b(before|after|except|excluding|unless|between|greater than|less than|not|without|since|last year|last quarter|this year|previous year|as of)\b",
        operation_text,
        re.I,
    ):
        return clarify(
            "This query needs an explicit supported scope. Only equality filters are supported; range/negation conditions are not inferred."
        )
    rows = [r for r in rows if any(f in r["values"] for f in fields)]
    if requested_quarters and not re.search(
        r"\bq[1-4]\b", " ".join(header_name(f) for f in fields)
    ):
        scoped = []
        for row in rows:
            periods = set(
                re.findall(
                    r"\bq[1-4]\b",
                    header_name(
                        row["sheet_or_page"]
                        + " "
                        + " ".join(
                            str(v)
                            for k, v in row["values"].items()
                            if header_name(k) in PERIODS
                        )
                    ),
                )
            )
            if not periods:
                return clarify(
                    "The requested period is not established for every relevant source. Clarify the unlabeled period."
                )
            if periods & requested_quarters:
                scoped.append(row)
        rows = scoped
    years = set(re.findall(r"\b20\d{2}\b", request.question))
    if years:
        if re.search(
            r"from\s+20\d{2}\s+to\s+20\d{2}|20\d{2}\s*[-–]\s*20\d{2}",
            request.question,
            re.I,
        ):
            return clarify(
                "List explicit required years; a range cannot be silently reduced to endpoints."
            )
        scoped = []
        for row in rows:
            known = set(
                re.findall(
                    r"\b20\d{2}\b",
                    " ".join(
                        fields
                        + [row["sheet_or_page"]]
                        + [
                            str(v)
                            for k, v in row["values"].items()
                            if header_name(k) in PERIODS
                        ]
                    ),
                )
            )
            if not known:
                return clarify(
                    "The requested year is not established for every relevant source. No year filter was silently ignored."
                )
            if known & years:
                scoped.append(row)
        rows = scoped

    filters: dict[str, set[str]] = {}
    for key, value in request.filters.items():
        if key not in headers or not value.strip():
            return clarify("A filter has an unknown field or empty value.")
        filters[key] = {value.strip()}
    if not filters:
        for key in headers:
            if key in fields:
                continue
            candidate_values = {
                str(r["values"][key])
                for r in rows
                if r["values"].get(key) is not None
                and (
                    number(r["values"][key]) is None
                    or header_name(key) in IDENTITIES | PERIODS
                )
            }
            found = {
                v
                for v in candidate_values
                if (len(v) >= 2 or header_name(key) in IDENTITIES | PERIODS)
                and contains(request.question, v)
            }
            if found:
                filters[key] = found
    if not request.filters and len(filters) > 1:
        named_filter_keys = {key for key in filters if contains(request.question, key)}
        if named_filter_keys:
            filters = {
                key: values
                for key, values in filters.items()
                if key in named_filter_keys
            }
        elif any(filters[a] & filters[b] for a in filters for b in filters if a != b):
            return clarify(
                "The requested labels match multiple fields. Select an explicit equality-filter field; no ambiguous combination was inferred."
            )
    clause = entity_clause(request.question, fields)
    if clause and not request.filters:
        identity_headers = [h for h in headers if header_name(h) in IDENTITIES]
        remainder = unmatched_terms(
            clause, [v for values in filters.values() for v in values], headers
        )
        if any(
            normalized_match.casefold() == clause.casefold()
            for _, normalized_match in re.findall(r"([\"'])(.+?)\1", request.question)
        ) and not any(h in filters for h in identity_headers):
            remainder = clause
        if remainder:
            explicit = [
                h
                for h in identity_headers
                if any(contains(request.question, a) for a in aliases(h))
            ]
            matched_identity = [h for h in identity_headers if h in filters]
            identity_candidates = explicit or matched_identity or identity_headers
            temporal = re.search(
                r"\b(last|previous|next|month|quarter|year|since|until|before|after)\b",
                remainder,
                re.I,
            )
            if len(identity_candidates) == 1 and not temporal:
                field = identity_candidates[0]
                matched_names = sorted(filters.get(field, set()))
                if matched_names:
                    return clarify(
                        f"I matched {field} "
                        + ", ".join(repr(v) for v in matched_names)
                        + f", but could not match or interpret {remainder!r} in this scope. Correct that name or qualifier, or ask only for the matched names; no subset was calculated.",
                        fields=fields,
                        unmatched_terms=[remainder],
                        matched_entities=matched_names,
                    )
                return QueryResponse(
                    status="no_evidence",
                    execution_path="structured",
                    answer=f"No matching {field} records were found for {remainder!r} in {source}"
                    + (
                        " within the selected source scope."
                        if request.sheet_or_page or request.source_scopes
                        else "."
                    ),
                    citations=[],
                    unresolved_citation_numbers=[],
                    context_count=0,
                    model=None,
                    generation_latency_seconds=0,
                    coverage={
                        "scope_records": len(rows),
                        "matched_records": 0,
                        "returned_records": 0,
                        "fields": fields,
                        "complete": True,
                        "requested_entity": remainder,
                        "entity_field": field,
                    },
                )
            return clarify(
                f"I could not resolve {remainder!r}. "
                + (
                    "Which field does this name belong to: "
                    + ", ".join(identity_candidates)
                    + "?"
                    if len(identity_candidates) > 1
                    else "Please state the intended name or qualifier; no constraint was ignored."
                ),
                fields=fields,
                unmatched_terms=[remainder],
                available_identity_fields=identity_candidates,
            )
    scope_count = len(rows)
    rows = [
        r
        for r in rows
        if all(
            any(cell_equal(r["values"].get(k), candidate) for candidate in v)
            for k, v in filters.items()
        )
    ]
    if not rows:
        return QueryResponse(
            status="no_evidence",
            execution_path="structured",
            answer="No source records match these fields and filters.",
            citations=[],
            unresolved_citation_numbers=[],
            context_count=0,
            model=None,
            generation_latency_seconds=0,
            coverage={
                "scope_records": scope_count,
                "matched_records": 0,
                "returned_records": 0,
                "complete": True,
            },
        )
    q = request.question.casefold()
    operation = request.operation
    if operation == "auto":
        sum_text = operation_text
        for filter_set in filters.values():
            for literal_value in filter_set:
                sum_text = re.sub(
                    r"(\b(?:for|of|among)\s+[\"']?)"
                    + re.escape(literal_value)
                    + r"(?!\w)",
                    r"\1<entity>",
                    sum_text,
                    flags=re.I,
                )
        if re.search(SUM_WORDS, sum_text, re.I):
            operation = "sum"
        elif (
            len(fields) >= 2 or len({r["sheet_or_page"] for r in rows}) == 2
        ) and re.search(
            r"\b(increase|grew|change)\b|from .+ to|strongest .+ growth", q
        ):
            operation = (
                "growth_percent"
                if re.search(r"\b(percent|percentage|rate)\b|%", q)
                else "increase"
            )
        elif re.search(r"\b(lowest|smallest|minimum|least)\b", q):
            operation = "minimum"
        elif re.search(r"\b(highest|largest|maximum|greatest|strongest)\b", q):
            operation = "maximum"
        else:
            operation = "lookup"
    if operation != "lookup" or request.record_scope != "auto":
        summary_labels = {
            "total",
            "totals",
            "subtotal",
            "sub total",
            "grand total",
            "all",
            "all regions",
        }
        flags = [
            any(
                header_name(k) in IDENTITIES and normalize(str(v)) in summary_labels
                for k, v in row["values"].items()
            )
            for row in rows
        ]
        if request.record_scope != "auto":
            rows = [
                row
                for row, summary in zip(rows, flags, strict=True)
                if summary == (request.record_scope == "summary")
            ]
            if not rows:
                return clarify(
                    "No records match the confirmed detail/summary selection."
                )
        elif any(flags) and not all(flags):
            response = clarify(
                "These sources contain summary/subtotal rows and detail records. Choose which population should supply the calculation; no double-counted total was asserted."
            )
            response.clarification_options = [
                {"label": "Use detail records", "record_scope": "detail"},
                {"label": "Use summary records", "record_scope": "summary"},
            ]
            return response
    if (
        operation == "sum"
        and len(rows) > 1
        and any(
            set(header_name(f).split())
            & {
                "average",
                "mean",
                "median",
                "rate",
                "ratio",
                "percentage",
                "percent",
                "margin",
                "index",
            }
            for f in fields
        )
    ):
        return clarify(
            "This measure is not automatically additive. Specify the business rule/weights; no unweighted total was asserted."
        )
    sheets = sorted({r["sheet_or_page"] for r in rows}, key=_natural_key)
    if (
        operation in {"increase", "growth_percent"}
        and len(fields) == 2
        and len({measure_name(f) for f in fields}) != 1
    ):
        return clarify(
            "Change calculations require the same measure in two ordered periods."
        )
    if operation == "sum" and any(
        header_name(f) in IDENTITIES | PERIODS for f in fields
    ):
        return clarify("Identifiers and period labels are not additive measures.")
    if operation == "sum" and len(fields) > 1:
        combined = combine_fields(request, source, rows, fields)
        if combined is not None:
            return combined
    if len(sheets) > 1 and operation != "lookup":
        comparison = compare_sources(request, source, rows, fields, operation)
        if comparison is not None:
            return comparison
        issue = union_issue(rows, fields, request)
        if issue:
            response = clarify(
                issue, available_scopes=sheets, matched_records=len(rows)
            )
            response.clarification_options = [
                {"label": s, "sheet_or_page": s} for s in sheets
            ]
            if "summary or detail" not in issue:
                response.clarification_options.append(
                    {
                        "label": "Use source records",
                        "aggregation_basis": "all_selected_records",
                    }
                )
            return response
    # Refuse the whole request visibly; silent truncation would certify an incomplete population.
    if len(rows) > MAX_ANSWER_RECORDS:
        return clarify(
            f"This answer would include {len(rows)} records. Narrow the scope to at most {MAX_ANSWER_RECORDS}; no records were silently truncated.",
            matched_records=len(rows),
        )
    entity_key = next(iter(filters)) if len(filters) == 1 else None
    normalized_question = normalize(request.question)

    def entity_position(row: dict[str, Any]) -> int:
        """Keep requested entity order separate from source values and citations."""
        if entity_key is None or len(filters[entity_key]) <= 1:
            return 0
        value = normalize(str(row["values"].get(entity_key, "")))
        match = re.search(
            r"(?<!\w)" + re.escape(value) + r"(?!\w)", normalized_question
        )
        return match.start() if match else len(normalized_question)

    # Presentation order must not assign a relevance-ranked amount to the wrong entity.
    rows.sort(
        key=lambda r: (
            entity_position(r),
            _natural_key(r["sheet_or_page"]),
            _natural_key(r["row_or_location"]),
        )
    )
    # Preserve caller/question metric order for changes from one field to another.
    if len(fields) == 2 and not request.fields:
        common = set(normalize(fields[0]).split()) & set(normalize(fields[1]).split())
        fields.sort(
            key=lambda f: min(
                (
                    q.find(t)
                    for t in normalize(f).split()
                    if t not in common and q.find(t) >= 0
                ),
                default=len(q),
            )
        )
    records = []
    citations = []
    missing = []
    lines = []
    labels = [
        h
        for h in headers
        if h not in fields
        and any(
            r["values"].get(h) is not None and number(r["values"].get(h)) is None
            for r in rows
        )
    ]
    # Show a common identity field and declared units, not unrelated columns
    # borrowed from other sheets. Requested missing cells remain explicit.
    common_headers = set.intersection(*(set(r["values"]) for r in rows))
    labels = [h for h in rows[0]["values"] if h in labels and h in common_headers]
    unit_labels = [
        h
        for h in headers
        if h in common_headers
        and normalize(h)
        in {"currency", "currency code", "unit", "units", "unit of measure"}
    ]
    labels = [h for h in labels if h not in unit_labels]
    selected = list(dict.fromkeys(list(filters) + labels[:1] + unit_labels + fields))
    for i, row in enumerate(rows, 1):
        metadata = SourceMetadata(source, row["sheet_or_page"], row["row_or_location"])
        rendered_values = {
            f: None if row["values"].get(f) is None else str(row["values"][f])
            for f in selected
        }
        records.append(
            EvidenceRecord(
                number=i,
                source_file=source,
                sheet_or_page=metadata.sheet_or_page,
                row_or_location=metadata.row_or_location,
                values=rendered_values,
                cell_references={
                    f: row["cell_origins"][f]
                    for f in selected
                    if f in row["cell_origins"]
                },
                merged_fields=[f for f in row["merged_fields"] if f in selected],
                cell_formats={
                    f: v
                    for f, v in row.get("cell_formats", {}).items()
                    if f in selected and v != "General"
                },
                formula_fields={
                    f: v
                    for f, v in row.get("formula_fields", {}).items()
                    if f in selected
                },
                continuation_fields={
                    f: v
                    for f, v in row.get("continuation_fields", {}).items()
                    if f in selected
                },
            )
        )
        citations.append(
            CitationResponse(
                number=i,
                source_file=source,
                sheet_or_page=metadata.sheet_or_page,
                row_or_location=metadata.row_or_location,
                citation_text=format_citation(metadata),
            )
        )
        content = "; ".join(
            f"{f}: {rendered_values[f] if rendered_values[f] is not None else 'Missing in source'}"
            for f in selected
        )
        content = content.replace("[", "［").replace("]", "］")
        location = format_citation(metadata).replace("[", "［").replace("]", "］")
        lines.append(f"- {location} — {content} (Source: [{i}])")
        for field in fields:
            if row["values"].get(field) is None:
                missing.append(
                    {
                        "number": i,
                        "field": field,
                        "cell": row["cell_origins"].get(field),
                    }
                )
    coverage: dict[str, object] = {
        "method": "all_indexed_rows",
        "record_scope": request.record_scope,
        "scope_records": scope_count,
        "matched_records": len(rows),
        "returned_records": len(records),
        "fields": fields,
        "missing_cells": missing,
        "complete": not missing,
    }
    response = QueryResponse(
        answer="\n".join(lines),
        status="incomplete" if missing else "answered",
        execution_path="structured",
        records=records,
        citations=citations,
        unresolved_citation_numbers=[],
        context_count=len(records),
        model=None,
        generation_latency_seconds=0,
        coverage=coverage,
    )
    if operation == "lookup":
        return response
    if operation == "sum":
        return sum_available(response, request, rows, fields)
    if missing:
        response.answer = (
            "Calculation withheld: requested values are missing in source records.\n"
            + response.answer
        )
        return response
    parsed = [[number(r["values"].get(f)) for f in fields] for r in rows]
    if any(n is None for row in parsed for n in row):
        response.status = "clarification_required"
        response.answer = (
            "Calculation withheld: a value is not a supported numeric format.\n"
            + response.answer
        )
        return response
    numeric = [[n for n in row if n is not None] for row in parsed]
    units = {
        source_unit(row, n[1])
        for row, numbers in zip(rows, numeric, strict=True)
        for n in numbers
    }
    if None in units or len(units) != 1:
        response.status = "clarification_required"
        response.answer = (
            "Calculation withheld: units/currencies are mixed, missing or inconsistent. No conversion was inferred.\n"
            + response.answer
        )
        return response
    if repeated_cells(rows, fields):
        response.status = "clarification_required"
        response.answer = (
            "Calculation withheld: a numeric merge anchor is shared by multiple rows; clarify allocation.\n"
            + response.answer
        )
        return response
    arithmetic = Context(prec=80)
    if operation in {"increase", "growth_percent"}:
        if len(fields) != 2:
            return clarify(
                "A change calculation requires exactly two ordered numeric fields."
            )
        if operation == "growth_percent" and any(row[0][0] == 0 for row in numeric):
            response.status = "incomplete"
            response.answer = (
                "Percentage growth is undefined for a zero baseline; no winner asserted.\n"
                + response.answer
            )
            response.coverage["calculation_complete"] = False
            return response
        values = [
            (
                arithmetic.subtract(row[1][0], row[0][0])
                if operation == "increase"
                else arithmetic.multiply(
                    arithmetic.divide(
                        arithmetic.subtract(row[1][0], row[0][0]), row[0][0]
                    ),
                    Decimal(100),
                )
            )
            for row in numeric
        ]
        # A negative direction request selects the minimum, not the maximum.
        want_min = bool(re.search(r"\b(smallest|lowest|least|minimum)\b", q))
        best = min(values) if want_min else max(values)
        winners = [i for i, value in enumerate(values, 1) if value == best]
        formatted = [
            (
                display(arithmetic.quantize(v, Decimal("0.01")))
                if operation == "growth_percent"
                else display(v)
            )
            for v in values
        ]
        result = {str(i): v for i, v in enumerate(formatted, 1)}
        summary = f"{operation} from {fields[0]} to {fields[1]}: " + "; ".join(
            f"{v} (Source: [{i}])" for i, v in enumerate(formatted, 1)
        )
        summary += (
            f". {'Minimum' if want_min else 'Maximum'}: {display(best)}; matching source records: "
            + ", ".join(f"[{i}]" for i in winners)
        )
    else:
        if len(fields) != 1:
            return clarify("Select exactly one numeric field for a minimum/maximum.")
        values = [row[0][0] for row in numeric]
        best = min(values) if operation == "minimum" else max(values)
        winners = [i for i, v in enumerate(values, 1) if v == best]
        result = {fields[0]: display(best)}
        summary = (
            f"{operation} {fields[0]}: {display(best)}; matching source records: "
            + ", ".join(f"[{i}]" for i in winners)
        )
    response.answer += "\n" + summary
    response.calculation = {
        "operation": operation,
        "fields": fields,
        "unit": "%" if operation == "growth_percent" else str(next(iter(units))),
        "rounding": (
            "Percentage results rounded to 2 decimal places; ranking uses unrounded values."
            if operation == "growth_percent"
            else "Exact decimal operands; no rounding"
        ),
        "result": result,
        "operands": [
            {
                "number": i,
                "values": {
                    f: display(numeric[i - 1][j][0]) for j, f in enumerate(fields)
                },
            }
            for i in range(1, len(rows) + 1)
        ],
    }
    return response
