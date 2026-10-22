# Local embedding adapter

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../../AUTHORS.md).

Decision owner and approver: **Imitiyaz**.

Status: implemented in application 0.3.8; this record explains the current choice and its trade-offs.

## Context and requirements

I use this component in the Document Desk MVP to support local processing, source identity and reproducible behavior. The choice below describes the implementation and its boundaries.

## Decision

Use the configured BGE SentenceTransformer behind an injected backend. Initialize once in application lifespan and bind name/dimension to a persistent index.

## Consequences and verification

Changing an embedding model can invalidate stored vectors. Synthetic encoder tests do not evaluate BGE quality. See [configuration](../configuration.md).

## Why this decision

Retain the established English local encoder and dimension/profile checks so retrieval changes can be compared against known evidence, rather than changing the model and architecture together.

## Options and trade-offs

The component fits the current fixtures and adapter contracts. Replacing it requires a representative benchmark, source/operand invariants and a migration/rollback plan. Adding another framework alone does not address factual correctness. See the [stack inventory](../technology-stack.md).

## Future reconsideration triggers

Revisit when an independently demonstrated document format, accuracy target, hardware limit, license requirement or deployment mode cannot be met. Define the acceptance cases before changing the dependency, preserve the old baseline, and compare extraction, correctness, latency/RAM and recovery. Compare proposed changes against explicit acceptance cases before replacing the component.
