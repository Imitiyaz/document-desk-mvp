# SPDX-License-Identifier: AGPL-3.0-only
"""Conservative literal subject checks for bounded narrative extraction.

This is a safety boundary for explicit names, identifiers and simple subject
phrases, not general named-entity recognition or an entailment proof. No aliases
are invented. Ambiguous pronouns and arbitrary paraphrases remain limitations.
Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import re

# Grammatical/question words are not identities. Domain names are deliberately
# absent: new projects and people must work without adding fixture vocabulary.
_GENERIC = set(
    "what when where who why how is are was were will would can could does do did has have please tell show summarize summarise explain according the a an and or in on at from to for of about document report file page section summary total quantity revenue hours next review production launch status approved approval date project product company customer annual overview scope it this that its they their january february march april may june july august september october november december monday tuesday wednesday thursday friday saturday sunday q1 q2 q3 q4".split()
)


def tokens(text: str) -> set[str]:
    """Compare whole Unicode words; Rose must not match Rosemary."""
    return set(re.findall(r"[^\W_]+(?:[-'][^\W_]+)*", text.casefold()))


def requested_anchors(question: str) -> list[str]:
    """Find explicit literal constraints without relying on source vocabulary."""
    result = [m.group(1) for m in re.finditer(r'["“]([^"”]+)["”]', question)]
    # Capitalized names anywhere, including the beginning of a question.
    for m in re.finditer(r"\b[A-Z][a-zA-Z0-9]*(?:[-'][A-Za-z0-9]+)*\b", question):
        if m.group().casefold() not in _GENERIC:
            result.append(m.group())
    for m in re.finditer(
        r"\b(?:project|initiative|customer|company|product|order|contract)\s+([\w-]+)",
        question,
        re.I,
    ):
        if m.group(1).casefold() not in _GENERIC:
            result.append(m.group(1))
    # Case-insensitive simple subject forms cover ordinary lowercase questions.
    subject_match = re.search(
        r"^\s*(?:is|was|will|can|has)\s+(?:the\s+)?(.+?)\s+(?:approved|authorized|scheduled|delayed|cancelled|canceled|permitted|ready|launched)\b",
        question,
        re.I,
    )
    if subject_match:
        result.extend(
            w
            for w in re.findall(r"[\w-]+", subject_match.group(1))
            if w.casefold() not in _GENERIC
        )
    # Preserve explicit business identifiers; never approximate them by similarity.
    result.extend(re.findall(r"\b[A-Za-z]+-\d+[A-Za-z0-9-]*\b", question))
    return list(dict.fromkeys(x for x in result if tokens(x)))


def supports_anchors(text: str, anchors: list[str]) -> bool:
    """Require all requested literal anchors in the same evidence passage."""
    available = tokens(text)
    return all(tokens(anchor) <= available for anchor in anchors)


def subject_passage(text: str, anchors: list[str]) -> str:
    """Keep named-subject sentences and their adjacent unnamed continuations.

    A new explicit name closes the previous subject window. This intentionally
    abstains on unsupported aliases and complex cross-sentence references.
    """
    if not anchors:
        return text
    selected: list[str] = []
    active = False
    requested = set().union(*(tokens(a) for a in anchors))
    for sentence in re.split(r"(?<=[.!?])\s+|\n\s*\n+", text):
        if supports_anchors(sentence, anchors):
            active = True
            selected.append(sentence)
        else:
            other = requested_anchors(sentence)
            if other and any(not tokens(name) <= requested for name in other):
                active = False
            if active:
                selected.append(sentence)
    return " ".join(selected)
