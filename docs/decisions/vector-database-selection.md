# Embedded Chroma adapter

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../../AUTHORS.md).

Decision owner and approver: **Imitiyaz**.

Status: implemented in application 0.3.8; this record explains the current choice and its trade-offs.

## Context and requirements

I use this component in the Document Desk MVP to support local processing, source identity and reproducible behavior. The choice below describes the implementation and its boundaries.

## Decision

Use a persistent embedded collection behind an injected interface, with source-scoped enumeration/deletion and explicit vectors.

## Consequences and verification

Pair vector backups with the source ledger. One process lock is not distributed consistency. See [architecture](../../ARCHITECTURE.md).

## Why this decision

The existing local vector adapter supports source-filtered similarity retrieval and persistence without operating a separate database server. Aggregation still reads the canonical ledger rather than relying on top-k search.

## Options and trade-offs

The component fits the current fixtures and adapter contracts. Replacing it requires a representative benchmark, source/operand invariants and a migration/rollback plan. Adding another framework alone does not address factual correctness. See the [stack inventory](../technology-stack.md).

## Future reconsideration triggers

Revisit when an independently demonstrated document format, accuracy target, hardware limit, license requirement or deployment mode cannot be met. Define the acceptance cases before changing the dependency, preserve the old baseline, and compare extraction, correctness, latency/RAM and recovery. Compare proposed changes against explicit acceptance cases before replacing the component.
