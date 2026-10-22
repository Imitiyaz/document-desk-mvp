# Local bounded narrative generation

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../../AUTHORS.md).

Decision owner and approver: **Imitiyaz**.

Status: implemented in application 0.3.8; this record explains the current choice and its trade-offs.

## Context and requirements

I use this component in the Document Desk MVP to support local processing, source identity and reproducible behavior. The choice below describes the implementation and its boundaries.

## Decision

Use Ollama through an HTTP adapter. Supported structured calculations do not rely on model-authored numbers. Narrative source selections are bounded and validated against original sentences.

## Consequences and verification

A correct quote can concern the wrong entity. Benchmark actual model/context behavior independently and respect latency/resource limits. See [limitations](../limitations.md).

## Why this decision

Ollama separates model service lifecycle from the API and retains local operation. The existing quantized Llama model is a benchmark baseline, not a guarantee of general reasoning.

## Options and trade-offs

The component fits the current fixtures and adapter contracts. Replacing it requires a representative benchmark, source/operand invariants and a migration/rollback plan. Adding another framework alone does not address factual correctness. See the [stack inventory](../technology-stack.md).

## Future reconsideration triggers

Revisit when an independently demonstrated document format, accuracy target, hardware limit, license requirement or deployment mode cannot be met. Define the acceptance cases before changing the dependency, preserve the old baseline, and compare extraction, correctness, latency/RAM and recovery. Compare proposed changes against explicit acceptance cases before replacing the component.
