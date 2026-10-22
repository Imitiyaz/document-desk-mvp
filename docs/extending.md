# Extending the application

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## Add a document type

1. Define extraction semantics and supported layouts before writing a loader.
2. Implement `BaseLoader` and emit the existing extracted-document contracts with source identity and physical locations.
3. Register the loader in `app/loaders/__init__.py`. The capabilities endpoint/UI discovers supported extensions there.
4. Add corrupt/encrypted/empty/budget and layout tests plus independently stated source facts.
5. Verify cleaning/chunking, complete ledger records, citations, upload errors and browser behavior.
6. Document new limitations, licenses and extraction-policy compatibility.

Do not silently convert unsupported content into plausible text or drop unparsed values. A new suffix is not sufficient evidence that the format is correctly supported.

## Add a calculation

Define population selection, units, missing/zero behavior, tie/rounding rules and exact expected operands. Keep arithmetic in deterministic tools. Extend request/response types, independent oracles, rendered answer tests and desktop/mobile comparisons together.

Never use ranked top-k retrieval to establish complete aggregation evidence. A full operand list is meaningful only if extraction and population selection are independently validated.

## Add a retrieval/model strategy

Establish the current baseline on representative documents and reserve questions from tuning. Measure entity/period relevance, evidence completeness, answer correctness, useful coverage, abstention, latency and memory separately.

Use injectable adapters and bounded tools. A model should not define its own authorization or silently change source scope. Preserve original/derived evidence distinctions and source lineage.

Changing a prompt or model can alter behavior without changing API schemas. Version and evaluate those changes explicitly. More agent steps, graphs or context do not automatically improve answers.

## Change conversation behavior

Model current request constraints and pending choices explicitly. Test rephrasing, new source sections, changed entities/groups, interrupted confirmation, expired contexts and new chats. Do not retain computed answers as authoritative facts or reuse a counting approval for a different population.

## Public documentation

Update the architecture/decision explanation, OpenAPI snapshot, examples and known limitations with each supported change. Keep private discussion transcripts, actual documents and machine-specific diagnostics outside source distribution.
