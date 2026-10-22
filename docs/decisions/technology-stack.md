# Small replaceable components

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../../AUTHORS.md).

Decision owner and approver: **Imitiyaz**.

Status: implemented in application 0.3.8; this record explains the current choice and its trade-offs.

## Context and requirements

I use this component in the Document Desk MVP to support local processing, source identity and reproducible behavior. The choice below describes the implementation and its boundaries.

## Decision

Use FastAPI/Pydantic for HTTP contracts, SQLite for source records, Chroma for vectors, SentenceTransformer for embeddings and Ollama for narrative generation. React/Vite provide the local UI.

## Consequences and verification

Inject heavy resources for tests. Additional frameworks or distributed services require a measured need. See [architecture](../../ARCHITECTURE.md).

## Why this decision

Typed HTTP contracts, a complete local source ledger and replaceable model adapters fit the bounded single-user product. Calculations remain deterministic; a general autonomous framework would add complexity without resolving evidence completeness.

## Options and trade-offs

The component fits the current fixtures and adapter contracts. Replacing it requires a representative benchmark, source/operand invariants and a migration/rollback plan. Adding another framework alone does not address factual correctness. See the [stack inventory](../technology-stack.md).

## Future reconsideration triggers

Revisit when an independently demonstrated document format, accuracy target, hardware limit, license requirement or deployment mode cannot be met. Define the acceptance cases before changing the dependency, preserve the old baseline, and compare extraction, correctness, latency/RAM and recovery. Compare proposed changes against explicit acceptance cases before replacing the component.
