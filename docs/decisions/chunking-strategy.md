# Row-aware chunks with complete source records

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../../AUTHORS.md).

Decision owner and approver: **Imitiyaz**.

Status: implemented in application 0.3.8; this record explains the current choice and its trade-offs.

## Context and requirements

I use this component in the Document Desk MVP to support local processing, source identity and reproducible behavior. The choice below describes the implementation and its boundaries.

## Decision

Preserve column labels and source coordinates in row fragments. Wide fragments aid retrieval; complete physical rows remain in the ledger for exact operations. Prose is split separately.

## Consequences and verification

Ranked fragments cannot prove a complete calculation population. Test wide rows, duplicate labels, paging and every operand. See [pipeline](../pipeline.md).

## Why this decision

Keep complete row identity and headers for table operations while bounding prose contexts. Wide-row fragments retain their parent identity so source/cell reconstruction does not depend on a fragment alone.

## Options and trade-offs

The component fits the current fixtures and adapter contracts. Replacing it requires a representative benchmark, source/operand invariants and a migration/rollback plan. Adding another framework alone does not address factual correctness. See the [stack inventory](../technology-stack.md).

## Future reconsideration triggers

Revisit when an independently demonstrated document format, accuracy target, hardware limit, license requirement or deployment mode cannot be met. Define the acceptance cases before changing the dependency, preserve the old baseline, and compare extraction, correctness, latency/RAM and recovery. Compare proposed changes against explicit acceptance cases before replacing the component.
