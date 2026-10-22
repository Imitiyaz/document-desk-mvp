# SPDX-License-Identifier: AGPL-3.0-only
"""Preserve requested entity groups, scopes and contributor provenance.

Each group/source combination is evaluated independently against the accepted
population. Whole-file results retain other physical rows. A missing cell, an
absent entity and a recorded zero have separate meanings throughout the API.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Structured
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Literal, cast

from app.api.schemas import (
    AnswerItem,
    EntityContribution,
    EvidenceRecord,
    GroupedResult,
    QueryRequest,
    QueryResponse,
)
from app.generation.answer_presenter import (
    answer_text,
    calculation_items,
    readable_value,
    safe_text,
)
from app.structured.cross_scope import IDENTITIES, PERIODS, UNIT_FIELDS
from app.structured.engine import (
    MAX_ANSWER_RECORDS,
    cell_equal,
    clarify,
    contains,
    header_name,
    normalize,
    table_answer,
)
from app.structured.intent import aliases, any_identity_breakdown, identity_breakdown


def contributor_instruction(question: str) -> tuple[str, bool]:
    """Remove only a bounded display instruction, never a data-selection clause."""
    pattern = (
        r"(?:[,;]\s*|\s+|^)(?:please\s+)?(?:include|show|give|with)\s+"
        r"(?:(?:the|a)\s+)?(?:(?:contributed|contributing|contributor|contribution)\s+)?"
        r"(?:region\s+details|region\s+contributions|contributor\s+details|"
        r"contribution\s+details|contributing\s+regions)"
        r"(?:\s+in\s+(?:the\s+)?results?)?\s*[?.!]*\s*$"
    )
    cleaned, count = re.subn(pattern, "", question, flags=re.I)
    return cleaned.strip(" ,;"), bool(count)


def group_intent(question: str) -> bool:
    """Recognize requested breakdowns or separate SUM clauses, not an entity union."""
    return (
        contributor_instruction(question)[1]
        or any_identity_breakdown(question)
        or bool(
            re.search(
                r"\b(?:individual|each|per)\s+(?:sheet|page|source)s?\b|\bby\s+(?:sheet|page|source)\b|\bgroup(?:ed|s)?\b",
                question,
                re.I,
            )
        )
        or bool(
            re.search(
                r"\band\s+(?:sum|total)\b|[?;]\s*(?:and\s+)?(?:sum|total)\b",
                question,
                re.I,
            )
        )
    )


def resolve_group_followup(
    request: QueryRequest, previous: QueryRequest, document: dict
) -> QueryRequest | None:
    """Inherit acknowledged measure/operation, not stale region selections or facts."""
    q = request.question.strip()
    cleaned, show_contributors = contributor_instruction(q)
    if show_contributors and not cleaned and previous.fields:
        return previous.model_copy(
            update={
                "conversation_id": request.conversation_id,
                "context_token": request.context_token,
                "document_id": request.document_id,
                "workspace_revision": request.workspace_revision,
                "question": contributor_instruction(previous.question)[0]
                + ", include contributed region details in the results",
                "page": 1,
            }
        )
    if not (
        group_intent(q) or previous.entity_groups or previous.breakdown != "none"
    ) or not re.match(
        r"^(and\b|what about\b|how about\b|also\b|now\b|same\b)", q, re.I
    ):
        return None
    if not previous.fields:
        return None
    words = set(header_name(q).split())
    explicit = [
        f
        for f in {f for r in document["rows"] for f in r["values"]}
        if set(header_name(f).split()) <= words
        and header_name(f) not in IDENTITIES | PERIODS | UNIT_FIELDS
    ]
    fields = explicit or request.fields or list(previous.fields)
    quarter = re.findall(r"\bQ[1-4]\b", q, re.I)
    if len(set(quarter)) == 1:
        fields = [
            re.sub(r"\bQ[1-4]\b", quarter[0].upper(), f, flags=re.I) for f in fields
        ]
    prefix = re.sub(
        r"^(?:and|what about|how about|also|now|same)\s*", "", q, flags=re.I
    )
    explicit_breakdown = bool(
        re.search(r"\b(?:individual|each|per|by)\s+(?:sheet|page|source)s?\b", q, re.I)
    )
    return request.model_copy(
        update={
            "fields": fields,
            "operation": "sum",
            "group_field": previous.group_field,
            "breakdown": "none" if explicit_breakdown else previous.breakdown,
            "question": "SUM " + " and ".join(fields) + ": " + prefix,
            "sheet_or_page": (
                request.sheet_or_page
                if "sheet_or_page" in request.model_fields_set
                else previous.sheet_or_page
            ),
            "source_scopes": (
                request.source_scopes
                if "source_scopes" in request.model_fields_set
                else previous.source_scopes
            ),
            "record_scope": (
                request.record_scope
                if "record_scope" in request.model_fields_set
                else previous.record_scope
            ),
            "aggregation_basis": (
                request.aggregation_basis
                if "aggregation_basis" in request.model_fields_set
                else previous.aggregation_basis
            ),
        }
    )


def plan_groups(
    request: QueryRequest, document: dict
) -> tuple[QueryRequest, QueryResponse | None]:
    """Plan only schema-grounded labels/measures; reject unknown clauses visibly."""
    if not (
        group_intent(request.question)
        or request.group_field
        or request.entity_groups
        or request.breakdown != "none"
    ):
        return request, None
    headers = sorted({f for r in document["rows"] for f in r["values"]})
    words = set(header_name(request.question).split())
    explicit = [
        f
        for f in headers
        if set(header_name(f).split()) <= words
        and header_name(f) not in IDENTITIES | PERIODS | UNIT_FIELDS
    ]
    fields = explicit or request.fields
    if len(fields) != 1 or fields[0] not in headers:
        return request, clarify(
            "Which exact measure should these grouped sums use? The previous measure is retained when an acknowledged chat supplies it.",
            available_fields=headers,
        )
    if request.operation not in {"auto", "sum"} or re.search(
        r"\b(average|count|median|weighted|convert|except|excluding|before|after|between|not|without)\b",
        request.question,
        re.I,
    ):
        return request, clarify(
            "This breakdown supports explicit SUM groups and equality filters. Other operations or conditions need a separate supported request."
        )
    quarters = set(re.findall(r"\bq[1-4]\b", request.question.casefold()))
    if quarters - set(re.findall(r"\bq[1-4]\b", fields[0].casefold())):
        return request, clarify(
            "The requested period does not match the available grouped measure; no previous period was substituted."
        )
    candidates: dict[str, list[str]] = {}
    for field in headers:
        if header_name(field) not in IDENTITIES:
            continue
        values = sorted(
            {
                str(r["values"][field])
                for r in document["rows"]
                if r["values"].get(field) is not None
            },
            key=len,
            reverse=True,
        )
        found = [v for v in values if contains(request.question, v)]
        if found:
            candidates[field] = found
    requested_breakdowns = identity_breakdown(request.question, headers)
    if len(requested_breakdowns) > 1:
        return request, clarify(
            "Choose one identity field for the per-entity breakdown: "
            + ", ".join(requested_breakdowns)
            + "."
        )
    group_field = request.group_field or (
        requested_breakdowns[0] if requested_breakdowns else None
    )
    if group_field is None and len(candidates) == 1:
        group_field = next(iter(candidates))
    if len(candidates) > 1 and group_field is None:
        return request, clarify(
            "The labels match more than one identity field. Select the group field explicitly."
        )
    if group_field is None:
        identities = {
            f
            for r in document["rows"]
            if fields[0] in r["values"]
            for f in r["values"]
            if header_name(f) in IDENTITIES
        }
        if len(identities) == 1:
            group_field = next(iter(identities))
    groups = request.entity_groups
    if requested_breakdowns and not groups and group_field:
        selected = (
            [request.sheet_or_page] if request.sheet_or_page else request.source_scopes
        )
        groups = [
            [v]
            for v in dict.fromkeys(
                str(r["values"][group_field])
                for r in document["rows"]
                if fields[0] in r["values"]
                and r["values"].get(group_field) is not None
                and (not selected or r["sheet_or_page"] in selected)
                and all(
                    cell_equal(r["values"].get(k), value)
                    for k, value in request.filters.items()
                    if k != group_field
                )
            )
        ]
        if candidates.get(group_field):
            groups = [[v] for v in candidates[group_field]]
    if not groups and group_field:
        text = request.question
        # A scope can precede later SUM clauses. Do not truncate the request at
        # its first 'in/from', or a fully restated follow-up loses every group.
        for phrase in fields + list({r["sheet_or_page"] for r in document["rows"]}):
            text = re.sub(
                r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", " ", text, flags=re.I
            )
        clauses = re.split(r"[?;,]|\band\s+(?:sum|total)\b", text, flags=re.I)
        for clause in clauses:
            group = [v for v in candidates.get(group_field, []) if contains(clause, v)]
            group.sort(key=lambda v: normalize(clause).find(normalize(v)))
            if group and group not in groups:
                groups = groups + [group]
    if len(groups) > 8:
        return request, clarify("Request at most eight separate entity groups at once.")
    if groups:
        if group_field not in headers:
            return request, clarify(
                "Select a group field present in the source schema."
            )
        known = {
            str(r["values"][group_field]).casefold()
            for r in document["rows"]
            if r["values"].get(group_field) is not None
        }
        if any(v.casefold() not in known for group in groups for v in group):
            return request, clarify(
                "A requested group label is absent from this document; no subset result was substituted."
            )
    remainder = normalize(contributor_instruction(request.question)[0])
    for phrase in sorted(
        fields
        + [v for g in groups for v in g]
        + list({r["sheet_or_page"] for r in document["rows"]}),
        key=len,
        reverse=True,
    ):
        remainder = re.sub(
            r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)", " ", remainder
        )
    allowed = set(
        "what is was are were the sum total of for and or from in file document workbook individual sheet sheets page pages source sources each by per all whole entire on separately both region regions group groups grouped overall please also records values amounts give show me their respectively now same about how".split()
    )
    allowed.update(
        word
        for h in headers
        if header_name(h) in IDENTITIES
        for alias in aliases(h)
        for word in alias.split()
    )
    breakdown = request.breakdown
    if breakdown == "none" and re.search(
        r"\b(?:individual|each|per|by)\s+(?:sheet|page|source)s?\b",
        request.question,
        re.I,
    ):
        breakdown = (
            "file_and_source"
            if re.search(
                r"\b(file|document|workbook|overall)\b", request.question, re.I
            )
            else "source"
        )
    # Understood constraints belong to the pending request even when unknown
    # words prevent execution. No numerical answer is used to reconstruct them.
    planned = request.model_copy(
        update={
            "fields": fields,
            "operation": "sum",
            "group_field": group_field,
            "entity_groups": groups,
            "breakdown": breakdown,
        }
    )
    unknown = sorted(set(remainder.split()) - allowed)
    if unknown:
        return planned, clarify(
            "I could not interpret these words in the grouped request: "
            + ", ".join(repr(word) for word in unknown)
            + ". Please rephrase that part or state its intended filter/operation explicitly. "
            + "Understood measure: "
            + fields[0]
            + "; SUM groups: "
            + ("; ".join(" + ".join(g) for g in groups) or "overall")
            + ". The pending request is retained; no subset was calculated.",
            fields=fields,
            unrecognized_terms=unknown,
        )
    return planned, None


def remap_calculation(
    child: QueryResponse, full: dict[tuple[str, str | int], EvidenceRecord]
) -> dict[str, Any] | None:
    """Bind every operand and exclusion to the shared original source numbering."""
    calculation = deepcopy(cast(dict[str, Any] | None, child.calculation))
    if calculation:
        by_number = {r.number: r for r in child.records}
        for operand in calculation["operands"]:
            record = by_number[operand["number"]]
            operand["number"] = full[
                (record.sheet_or_page, record.row_or_location)
            ].number
            operand["source"] = {
                k: getattr(record, k)
                for k in ("source_file", "sheet_or_page", "row_or_location")
            }
            operand["cell_references"] = {
                f: record.cell_references[f]
                for f in operand["values"]
                if f in record.cell_references
            }
        for exclusion in calculation["excluded_cells"]:
            record = by_number[exclusion["number"]]
            exclusion["number"] = full[
                (record.sheet_or_page, record.row_or_location)
            ].number
    return calculation


def contributions(
    entities: list[str],
    group_field: str | None,
    subset: list[dict],
    base: QueryRequest,
    source: str,
    document: dict,
    full: dict[tuple[str, str | int], EvidenceRecord],
) -> list[EntityContribution]:
    """Calculate every requested entity; blanks, absence and true zero stay distinct."""
    if not group_field:
        return []
    labels: list[str | None] = (
        list(entities)
        if entities
        else list(dict.fromkeys(r["values"].get(group_field) for r in subset))
    )
    result = []
    for entity in labels:
        rows = [
            r
            for r in subset
            if (
                r["values"].get(group_field) is None
                if entity is None
                else cell_equal(r["values"].get(group_field), entity)
            )
        ]
        if not rows:
            result.append(
                EntityContribution(
                    entity=entity, status="no_evidence", record_numbers=[]
                )
            )
            continue
        child = table_answer(base, source, {**document, "rows": rows})
        assert child is not None
        records = [full[(r["sheet_or_page"], r["row_or_location"])] for r in rows]
        result.append(
            EntityContribution(
                entity=entity,
                status=cast(Any, child.status),
                record_numbers=[r.number for r in records],
                calculation=remap_calculation(child, full),
                missing_cells=[
                    {"number": r.number, "field": f, "cell": r.cell_references.get(f)}
                    for r in records
                    for f in base.fields
                    if r.values.get(f) is None
                ],
            )
        )
    return result


def contribution_items(
    title: str, values: list[EntityContribution], group_field: str | None
) -> list[AnswerItem]:
    """Expose entity results in the plain API answer as well as the browser."""
    items = []
    for value in values:
        label = (
            safe_text(value.entity)
            if value.entity is not None
            else f"{safe_text(group_field or 'Entity')} not recorded"
        )
        if value.status == "no_evidence":
            detail = "no matching source records; contribution unknown, not zero."
        elif value.calculation:
            calc = cast(dict[str, Any], value.calculation)
            detail = "; ".join(
                f"{safe_text(f)}: {readable_value(v)}"
                + (" " + safe_text(calc["unit"]) if calc["unit"] else "")
                for f, v in calc["result"].items()
            ) + (
                "; available-value subtotal; some source values are missing."
                if calc.get("partial")
                else "."
            )
        elif value.missing_cells:
            detail = "missing in source; no numeric contribution or zero was invented."
        else:
            detail = "calculation needs clarification; no contribution was inferred."
        items.append(
            AnswerItem(
                kind="notice",
                text=title + " · " + label + " — " + detail,
                citation_numbers=value.record_numbers,
            )
        )
    return items


def grouped_answer(
    request: QueryRequest, source: str, document: dict
) -> QueryResponse | None:
    """Evaluate each group/scope separately; overall totals never drop other rows."""
    if not request.entity_groups and request.breakdown == "none":
        return None
    rows = document["rows"]
    selected_scopes = (
        [request.sheet_or_page] if request.sheet_or_page else request.source_scopes
    )
    if selected_scopes:
        known = {r["sheet_or_page"] for r in rows}
        if set(selected_scopes) - known:
            return clarify("One or more requested source sections are absent.")
        rows = [r for r in rows if r["sheet_or_page"] in selected_scopes]
    rows = [r for r in rows if request.fields[0] in r["values"]]
    for field, value in request.filters.items():
        if field == request.group_field:
            continue
        if not any(field in r["values"] for r in rows):
            return clarify("An equality filter uses an unknown field.")
        rows = [r for r in rows if cell_equal(r["values"].get(field), value)]
    if not rows:
        return clarify("No table records match the requested measure and source scope.")
    scopes = list(dict.fromkeys(r["sheet_or_page"] for r in rows))
    if (
        len(rows) > MAX_ANSWER_RECORDS
        or (len(scopes) + 1) * (len(request.entity_groups) + 1) > 64
    ):
        return clarify(
            "This breakdown is too large. Narrow the sources or entity groups; no partial population was calculated."
        )
    wants_overall = request.breakdown != "none" or bool(
        re.search(r"\boverall\b|\bgrand\s+total\b", request.question, re.I)
    )
    if request.entity_groups and not wants_overall:
        named_values = {v for g in request.entity_groups for v in g}
        if (
            request.group_field
            and identity_breakdown(request.question, [request.group_field])
            and any(r["values"].get(request.group_field) is None for r in rows)
            and not any(contains(request.question, v) for v in named_values)
        ):
            return clarify(
                f"Some {request.group_field} labels are missing. Include an overall total to retain those unlabelled records separately; no amounts were assigned to a product or dropped."
            )
        rows = [
            r
            for r in rows
            if any(
                cell_equal(r["values"].get(request.group_field), v)
                for v in named_values
            )
        ]
    source_doc = {**document, "rows": rows}
    base = request.model_copy(
        update={
            "question": "SUM " + request.fields[0],
            "sheet_or_page": None,
            "source_scopes": [],
            "filters": {},
            "entity_groups": [],
            "breakdown": "none",
        }
    )
    # Existing period/unit/summary/allocation guards must approve the full population.
    overall_request = (
        base.model_copy(update={"operation": "lookup", "question": request.fields[0]})
        if request.breakdown == "source"
        else base
    )
    overall = table_answer(overall_request, source, source_doc)
    if overall is None:
        return clarify("The requested grouped measure could not be resolved.")
    if overall.status == "clarification_required":
        return overall
    full = {(r.sheet_or_page, r.row_or_location): r for r in overall.records}
    # Reuse the engine's accepted detail/summary population. Contributors must
    # not reintroduce excluded summary rows or refer to absent shared records.
    rows = [r for r in rows if (r["sheet_or_page"], r["row_or_location"]) in full]
    items: list[AnswerItem] = []
    results: list[GroupedResult] = []
    populations: list[tuple[str, list[dict]]] = []
    if request.breakdown != "source":
        populations.append(
            ("Selected sources" if selected_scopes else "Whole file", rows)
        )
    if request.breakdown != "none":
        populations += [
            (s, [r for r in rows if r["sheet_or_page"] == s]) for s in scopes
        ]
    groups: list[tuple[str, list[str]]] = (
        [("Overall", [])]
        if request.breakdown != "none"
        or not request.entity_groups
        or re.search(r"\boverall\b|\bgrand\s+total\b", request.question, re.I)
        else []
    )
    # Overall and named groups coexist: a grouped subtotal must not replace the whole-file result.
    entity_groups = request.entity_groups
    if request.group_field and identity_breakdown(
        request.question, [request.group_field]
    ):
        entity_groups = [
            [v]
            for v in dict.fromkeys(
                str(r["values"][request.group_field])
                for r in rows
                if r["values"].get(request.group_field) is not None
                and any(
                    str(r["values"][request.group_field]) in group
                    for group in request.entity_groups
                )
            )
        ]
    groups += [(" + ".join(g), g) for g in entity_groups]
    for scope, population in populations:
        for label, entities in groups:
            subset = [
                r
                for r in population
                if not entities
                or any(
                    cell_equal(r["values"].get(request.group_field), v)
                    for v in entities
                )
            ]
            # Absence of a row differs from a matched row with an empty revenue cell.
            missing_entities = [
                v
                for v in entities
                if not any(
                    cell_equal(r["values"].get(request.group_field), v) for r in subset
                )
            ]
            title = f"{scope} · {label}"
            contributor_values = contributions(
                entities, request.group_field, subset, base, source, document, full
            )
            if not subset:
                text = title + ": no matching source records; no zero was inferred."
                absent_items = [
                    AnswerItem(kind="notice", text=text)
                ] + contribution_items(title, contributor_values, request.group_field)
                results.append(
                    GroupedResult(
                        label=label,
                        scope=scope,
                        entities=entities,
                        status="no_evidence",
                        answer=answer_text(absent_items),
                        record_numbers=[],
                        missing_entities=missing_entities,
                        contributions=contributor_values,
                    )
                )
                items.extend(absent_items)
                continue
            child = table_answer(base, source, {**document, "rows": subset})
            assert child is not None
            calculation = remap_calculation(child, full)
            if calculation:
                if missing_entities:
                    calculation["partial"] = True
                child.calculation = calculation
            child.records = [
                full[(r.sheet_or_page, r.row_or_location)] for r in child.records
            ]
            if missing_entities and child.status == "answered":
                child.status = "incomplete"
            child_items = (
                calculation_items(child, base, child.records)
                if calculation
                else [AnswerItem(kind="notice", text=child.answer)]
            )
            for line in child_items:
                line.text = title + ": " + line.text
            if missing_entities:
                child_items.append(
                    AnswerItem(
                        kind="notice",
                        text=title
                        + ": no records for "
                        + ", ".join(missing_entities)
                        + "; their contribution is unknown, not zero.",
                    )
                )
            items.extend(child_items)
            entity_items = contribution_items(
                title, contributor_values, request.group_field
            )
            items.extend(entity_items)
            results.append(
                GroupedResult(
                    label=label,
                    scope=scope,
                    entities=entities,
                    status=cast(
                        Literal[
                            "answered",
                            "incomplete",
                            "no_evidence",
                            "clarification_required",
                        ],
                        child.status,
                    ),
                    answer=answer_text(child_items + entity_items),
                    record_numbers=[r.number for r in child.records],
                    missing_entities=missing_entities,
                    calculation=calculation,
                    contributions=contributor_values,
                )
            )
    overall.grouped_results = results
    overall.calculation = None
    if any(r.continuation_fields for r in overall.records):
        items.insert(
            0,
            AnswerItem(
                kind="notice",
                text="Region continuation rule applied: original blank cells and their prior Region anchors remain in the evidence. No missing revenue was filled.",
                citation_numbers=[
                    r.number for r in overall.records if r.continuation_fields
                ],
            ),
        )
    overall.answer_items = items
    overall.answer = answer_text(items)
    overall.status = (
        "incomplete"
        if any(r.status in {"incomplete", "no_evidence"} for r in results)
        else "answered"
    )
    if any(r.status == "clarification_required" for r in results):
        overall.status = "clarification_required"
    overall.coverage.update(
        method="all_indexed_rows_grouped",
        complete=overall.status == "answered",
        grouped_results=len(results),
        fields=request.fields,
        group_field=request.group_field,
        population_basis=request.aggregation_basis,
    )
    return overall
