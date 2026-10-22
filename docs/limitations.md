# Known limitations and deployment readiness

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## Answer correctness

**Narrative relevance and entailment remain bounded.** The reported explicit Rose/Orchid substitution is covered by literal-subject checks and focused live positive/negative verification. That correction is not general entity resolution: aliases, pronouns, mixed subjects and unsupported language can still be misinterpreted or conservatively refused. Exact quotations and resolved citations do not prove the intended relationship was answered. Independently inspect narrative evidence before acting on it.

Natural-language understanding is implemented through bounded rules and schemas. Unsupported phrasings, qualifiers, groups or follow-ups can be rejected or misinterpreted. The system is not a general reasoning assistant.

Structured arithmetic is deterministic over selected records; the result can still be wrong for the user's intent if extraction, label continuation, scope, units or record population is wrong. Validate the operands and business meaning.

## Document and data constraints

- Only XLSX/XLSM and text-based PDF are registered. XLS, image-only PDFs and general OCR are unsupported.
- Spreadsheet interpretation has layout assumptions. The Region continuation rule is domain-specific.
- Formula caches are read, not recalculated or certified fresh.
- Complex headers, tables, footnotes and PDF reading order can be misinterpreted.
- Missing values remain unknown. Subtotals are not complete totals.
- Cross-sheet overlap and summary/detail duplication require a justified counting basis.
- The UI selects one document; general cross-file research is not implemented.
- Bounded narrative evidence and summaries do not establish exhaustive recall.

## Runtime and operations

Run one process/worker. Operations are serialized and conversations are in memory. Authentication, multi-user isolation, distributed consistency, background indexing and rate limiting are not implemented. NGINX provides static serving and an API proxy in the Compose deployment; this does not add those missing service capabilities.

Real Windows Docker build, host-model connection, persistence/recreation, isolated restore and honest unavailable-model fallback have been reviewed for the documented runtime. Your own deployment still needs its clean-install checks. TLS, public hosting and multi-user access controls remain outside this local topology.

No universal RAM/latency or corpus-size guarantee is supplied. Extraction ceilings prevent selected over-budget inputs but do not guarantee acceptable response time. Resource measurement must attribute the API, model server, child processes and any GPU separately.

## Evidence limits

Passing synthetic tests is not representative business acceptance. Controlled browser checks use substitute embeddings/LLM responses; focused actual-model Orchid/Rose checks are separate evidence. Automated desktop keyboard/width tests do not replace owner visual feedback or certify every assistive technology. Physical mobile devices, unusual workbooks and hostile documents need explicit evaluation.

A prior model-service call failed with LLMConnectionError; later actual calls succeeded. Its underlying cause is unconfirmed. Successful narrative requests took roughly 38–39 seconds on the reviewed laptop; this is an observation, not a latency target or measured p95. RAM/process attribution, capacity limits and representative business coverage remain conditional. See [verification](validation.md).

## Before a production deployment

Define and implement access/data isolation, secure serving and secrets management; independently validate representative documents and unanswerable cases; resolve narrative identity failures; measure operating limits; test recovery and incident handling; review dependency/model licenses; and run the intended platform/release pipeline.

These are engineering gaps to address, not controls silently supplied by setting `APP_ENV=production`.

## Literal narrative subjects in 0.3.8

The reported Rose/Orchid substitution is addressed for explicit literal names, identifiers and supported simple subject forms. Whole-word comparisons prevent substring aliases; adjacent source windows help keep a matching subject's dates with that subject. Unknown covered names abstain before generation. Empty model selections also abstain.

This is a conservative safety control, not general NER, natural-language planning or an entailment proof. Aliases, complex pronouns, ambiguous mixed subjects, case/wording outside supported forms and multilingual names require further evaluation. A conservative no-evidence response may still need human review; do not infer that the document has no information anywhere.

## Desktop presentation boundary

The MVP targets desktop browsers. Mobile-specific layout and acceptance are outside the supported scope. Layout screenshots and keyboard checks must be reviewed on the target desktop/browser; component passes alone are insufficient.
