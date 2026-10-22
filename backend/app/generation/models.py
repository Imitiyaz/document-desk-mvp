# SPDX-License-Identifier: AGPL-3.0-only
"""The Stage 7 -> Stage 8/9 contract: what prompt assembly produces.

`AssembledPrompt` is deliberately a structured type, not a raw string --
Stage 8 (LLM Integration) needs `.text` to send to Ollama, and Stage 9
(Citation Resolution) needs `.citation_map` to turn a model's "[2]"
reference back into a real `SourceMetadata` without ever having to trust
the model to transcribe a filename, sheet name, or row number correctly.
Handing back only a string would force some later stage to re-derive that
mapping from the text itself -- exactly the "citation reconstructed after
the fact" anti-pattern `ARCHITECTURE.md` rules out for every other stage
in this pipeline.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Generation
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.models.extracted import SourceMetadata
from app.retrieval.models import RetrievalResult


@dataclass(frozen=True)
class AssembledPrompt:
    """A fully assembled prompt, ready to send to an LLM, plus everything
    needed to resolve its citations afterward.

    Attributes:
        text: The complete prompt string (system instructions + numbered
            context + question), exactly as it should be sent to the LLM.
        citation_map: Numbered context index (matching the `[N]` markers
            inside `text`) -> the `SourceMetadata` that chunk actually
            came from. Built here, from data already trusted at
            ingestion time -- never something a later stage has to
            reconstruct by parsing the model's own output.
        answer_mode: Prose is preserved verbatim; records require a validated JSON selection.
        context_used: The `RetrievalResult`s actually included in the
            prompt, in the same order as their `[N]` numbering. Empty if
            no relevant chunks were retrieved -- a valid, expected case
            (see `build_prompt`'s docstring), not an error condition.
    """

    text: str
    citation_map: dict[int, SourceMetadata]
    context_used: list[RetrievalResult]
    answer_mode: Literal["prose", "records"] = "prose"
    json_output: bool = False


@dataclass(frozen=True)
class GeneratedAnswer:
    """The Stage 8 -> Stage 9 contract: a real LLM response, plus
    everything needed to resolve it.

    Deliberately carries the originating `AssembledPrompt`, not just the
    raw answer text -- Stage 9 (Citation Resolution) needs `prompt.citation_map`
    to turn the model's `[2]`-style references in `raw_text` into real
    citations, and bundling it here means Stage 9 doesn't need a second
    parameter threaded alongside the answer just to carry that map.

    Attributes:
        raw_text: The model's response, exactly as returned -- not yet
            parsed for citations (that's Stage 9's job) or otherwise
            post-processed.
        prompt: The `AssembledPrompt` that produced this answer. Carries
            `citation_map` (for Stage 9) and `context_used` (for
            debugging "why did it say that" without re-deriving it).
        model: The actual model name used to generate this answer (from
            `settings.ollama_model` at call time) -- recorded on the
            answer itself so a later change to the configured model
            doesn't retroactively make old logged answers ambiguous
            about which model produced them.
        latency_seconds: Wall-clock time the generation call took.
            Observability, not a correctness concern -- useful for
            noticing when CPU-only inference (documented as expected to
            be slow in docs/decisions/local-llm-selection.md) is the
            actual bottleneck versus something else.
    """

    raw_text: str
    prompt: AssembledPrompt
    model: str
    latency_seconds: float


@dataclass(frozen=True)
class ResolvedCitation:
    """One citation the model actually used in its answer, resolved back
    to the real source it refers to.

    Attributes:
        number: The `[N]` number exactly as it appeared in the answer
            text -- kept so a caller can cross-reference this citation
            back to a specific `[N]` marker in `GeneratedAnswer.raw_text`
            if needed (e.g. to render a clickable footnote).
        metadata: The real `SourceMetadata` this number resolved to, via
            `AssembledPrompt.citation_map` -- never re-derived from the
            model's own text, per this project's citation design (see
            `AssembledPrompt`'s docstring).
        citation_text: A human-readable "file / sheet / row" string,
            matching the format already used throughout this project's
            manual smoke tests and logs -- kept consistent rather than
            inventing a new display format here.
    """

    number: int
    metadata: SourceMetadata
    citation_text: str


@dataclass(frozen=True)
class Answer:
    """The Stage 9 -> Stage 10 (API) contract: a fully resolved, citable
    answer, ready to serialize into an API response.

    Attributes:
        text: In prose mode, the model's answer, verbatim. In records mode,
            source text rendered in source-location order. `[N]` markers are left
            exactly as the model wrote them. Deliberately NOT rewritten
            here; how a citation marker gets displayed (inline footnote,
            hover tooltip, etc.) is a presentation decision for Stage 11
            (React Frontend), not something to bake into this stage.
        citations: Every citation number the model actually used,
            resolved to a real source, deduplicated and ordered by first
            appearance in `text` -- not by citation number order, since
            a model can reference `[2]` before `[1]`.
        unresolved_citation_numbers: Citation numbers the model referenced
            that do NOT exist in the originating `citation_map` -- e.g.
            the model wrote `[5]` when only 3 context chunks were ever
            provided. A real, visible signal worth surfacing (a
            plausible hallucinated source), not something to silently
            drop just because it doesn't resolve.
        model: Carried through from `GeneratedAnswer.model`.
        latency_seconds: Carried through from `GeneratedAnswer.latency_seconds`.
    """

    text: str
    citations: list[ResolvedCitation]
    unresolved_citation_numbers: list[int]
    model: str
    latency_seconds: float
