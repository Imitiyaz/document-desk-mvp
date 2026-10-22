# SPDX-License-Identifier: AGPL-3.0-only
"""The Stage 6 -> Stage 7 contract: what a retrieval query returns.

Deliberately a separate type from vectorstore.models.RetrievedMatch,
even though the fields overlap heavily. RetrievedMatch is a *raw* query
result -- it carries `distance`, ChromaDB's native "smaller is more
similar" cosine distance, because that's what a vector collection
actually returns. RetrievalResult is what this stage produces *from*
that raw result: a `score` (bigger is more similar -- the sign is
flipped, deliberately, to match how a human or an LLM prompt intuitively
reads "relevance"), plus an explicit `rank`. Keeping these as two types,
not one, means a type checker catches a caller accidentally treating a
raw distance as if it were a similarity score, or vice versa -- the same
reasoning `CleanedRow` vs. `ExtractedRow` was kept separate for in
Stage 2.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Retrieval
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.extracted import SourceMetadata


@dataclass(frozen=True)
class RetrievalResult:
    """One ranked result from a retrieval query.

    Attributes:
        text: The chunk's embeddable text (a rendered row sentence, or a
            piece of narrative text).
        metadata: Citation metadata -- source_file, sheet_or_page,
            row_or_location. Carried through unchanged from ingestion
            time, per the project's citation design (never reconstructed
            after the fact).
        score: Cosine similarity, bigger is more similar. Range is
            theoretically [-1, 1] for normalized vectors, but in
            practice sits in [0, 1] for genuinely related text -- two
            embeddings pointing in opposite directions (score near -1
            or below 0) would mean "unrelated," not "relevant."
        rank: 1-indexed position in this result set (1 = best match).
            Stored explicitly rather than left implicit in list order,
            so Stage 7's prompt assembly (or a future re-ranking step)
            can label sources ("Source 1", "Source 2", ...) without
            recomputing position from a list index.
    """

    text: str
    metadata: SourceMetadata
    score: float
    rank: int
