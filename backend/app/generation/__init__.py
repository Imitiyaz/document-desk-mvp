# SPDX-License-Identifier: AGPL-3.0-only
"""Stage 7: Prompt assembly -- turns a question + retrieved chunks into
the exact prompt sent to the LLM, with a citation map for Stage 9.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Generation
"""

from __future__ import annotations

from app.generation.citation_resolver import resolve_citations
from app.generation.llm_client import LLMClient
from app.generation.models import (
    Answer,
    AssembledPrompt,
    GeneratedAnswer,
    ResolvedCitation,
)
from app.generation.prompt_builder import RECOMMENDED_TEMPERATURE, build_prompt

__all__ = [
    "AssembledPrompt",
    "GeneratedAnswer",
    "Answer",
    "ResolvedCitation",
    "build_prompt",
    "RECOMMENDED_TEMPERATURE",
    "LLMClient",
    "resolve_citations",
]
