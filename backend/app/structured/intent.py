# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded schema-aware entity phrases and aggregation wording.

Unknown labels are parsed independently of the values that happen to exist in a
file. An unmatched constraint must never become an unconstrained table request.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import re

from app.structured.cross_scope import IDENTITIES

SUM_WORDS = (
    r"\b(?:total|totals|sum|combined|totally|altogether)\b|\badd\s+(?:them\s+)?up\b"
)


def normalized(text: str) -> str:
    """Use whole words without substring matches on identifiers."""
    return " ".join(re.findall(r"\w+", text.casefold()))


def phrase_pattern(phrase: str) -> str:
    """Match literal source labels with harmless spaces/hyphens, not substrings."""
    return (
        r"(?<!\w)"
        + r"[\W_]+".join(re.escape(w) for w in normalized(phrase).split())
        + r"(?!\w)"
    )


def aliases(field: str) -> set[str]:
    """Derive singular/plural forms from the schema, never fixture-specific names."""
    text = normalized(field)
    plural = text[:-1] + "ies" if text.endswith("y") else text + "s"
    return {text, plural}


def identity_breakdown(question: str, headers: list[str]) -> list[str]:
    """Find explicit per-identity instructions; source/page breakdown is separate."""
    result = []
    for field in headers:
        if normalized(field) not in IDENTITIES:
            continue
        names = "|".join(phrase_pattern(a) for a in aliases(field))
        if re.search(
            r"\b(?:individual|each|per|by)\s+(?:the\s+)?(?:" + names + ")",
            question,
            re.I,
        ):
            result.append(field)
    return result


def any_identity_breakdown(question: str) -> bool:
    """Identify supported identity vocabulary before a conversation has its schema."""
    return bool(identity_breakdown(question, sorted(IDENTITIES))) and bool(
        re.search(SUM_WORDS, question, re.I)
    )


def entity_clause(question: str, fields: list[str]) -> str | None:
    """Recognize for/among, measure-of, and a bounded entity-before-measure form."""
    quoted = re.search(r"\b(?:for|among)\s+([\"'])(.+?)\1", question, re.I)
    if quoted:
        return quoted.group(2)
    stop = r"(?:\b(?:in|on|from|according|which)\b|[?]|$)"
    found = re.search(r"\b(?:for|among)\s+(.+?)" + stop, question, re.I)
    if found:
        return found.group(1).strip()
    for field in sorted(fields, key=len, reverse=True):
        if not re.search(phrase_pattern(field), question, re.I):
            continue
        quoted = re.search(
            phrase_pattern(field) + r"\s+of\s+([\"'])(.+?)\1", question, re.I
        )
        if quoted:
            return quoted.group(2)
        found = re.search(
            phrase_pattern(field) + r"\s+of\s+(.+?)" + stop, question, re.I
        )
        if found:
            return found.group(1).strip()
        before = re.split(phrase_pattern(field), question, maxsplit=1, flags=re.I)[0]
        before = re.sub(
            r"^(?:what\s+(?:(?:is|was|are|were)\s+)?(?:the\s+)?)",
            "",
            before,
            flags=re.I,
        ).strip()
        # Longer descriptive prefixes (e.g. two-period comparisons) retain the
        # existing planner. Only a bare or quoted entity is interpreted here.
        if re.fullmatch(r"[\w-]+|[\"'][^\"']+[\"']", before) and not re.fullmatch(
            SUM_WORDS
            + r"|minimum|maximum|lowest|highest|strongest|weakest|largest|smallest|greatest|least|increase|growth|change|percentage|percent|which|who|where|when|why|how|show|list",
            before,
            re.I,
        ):
            return before.strip("\"'")
    return None


def unmatched_terms(clause: str, values: list[str], fields: list[str]) -> str:
    """Remove only recognized labels and harmless grammar, retaining unknown terms."""
    remaining = clause
    for phrase in sorted(values + fields, key=len, reverse=True):
        remaining = re.sub(phrase_pattern(phrase), " ", remaining, flags=re.I)
    grammar = {
        "the",
        "and",
        "or",
        "all",
        "each",
        "only",
        "just",
        "total",
        "totals",
        "sum",
        "combined",
        "totally",
        "altogether",
        "region",
        "regions",
        "order",
        "orders",
    }
    grammar.update(w for f in fields for a in aliases(f) for w in a.split())
    remaining = re.sub(
        r"\b(?:" + "|".join(sorted(grammar, key=len, reverse=True)) + r")\b",
        " ",
        remaining,
        flags=re.I,
    )
    return " ".join(remaining.strip(" \t\r\n\"'?.!,").split())
