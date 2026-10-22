# Explicit quality-tool versions

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../../AUTHORS.md).

Decision owner and approver: **Imitiyaz**.

Status: implemented in application 0.3.8; this record explains the current choice and its trade-offs.

## Context and requirements

I use this component in the Document Desk MVP to support local processing, source identity and reproducible behavior. The choice below describes the implementation and its boundaries.

## Decision

Pin Black, Ruff, mypy and pytest so rule/format behavior is reproducible across review environments. CI and local checks use the same pins.

## Consequences and verification

Direct pins do not lock transitive native packages or model weights. Review dependency updates and record resolved release environments. See [development](../development.md).

## Why this decision

Explicit direct pins and a frontend lockfile reduce accidental upgrades. They do not make transitive Python resolution or moving container tags immutable; record the actual environment for a release.

## Options and trade-offs

The component fits the current fixtures and adapter contracts. Replacing it requires a representative benchmark, source/operand invariants and a migration/rollback plan. Adding another framework alone does not address factual correctness. See the [stack inventory](../technology-stack.md).

## Future reconsideration triggers

Revisit when an independently demonstrated document format, accuracy target, hardware limit, license requirement or deployment mode cannot be met. Define the acceptance cases before changing the dependency, preserve the old baseline, and compare extraction, correctness, latency/RAM and recovery. Compare proposed changes against explicit acceptance cases before replacing the component.
