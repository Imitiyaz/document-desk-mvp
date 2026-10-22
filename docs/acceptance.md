# Supported scope and acceptance boundaries

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## Intended use

Document Desk MVP **0.3.8** is a local, single-user learning and reference application. The documented scope is intentionally bounded. Its tested extraction, original-cell provenance, deterministic calculations, bounded conversations, desktop UI and Docker deployment are useful delivered capabilities; they are not a general assistant or a production-certified multi-user service.

Use the application within the conditions below. Start with [native setup](setup.md) or [Docker deployment](docker.md).

## Supported areas and evidence boundaries

**Table ACC-01 — Delivered areas and their acceptance boundaries.**

| Area | Delivered and observed | Remaining boundary |
| --- | --- | --- |
| Parsing, search and source ledger | Supported PDF/Excel extraction, original records/cells, BGE/Chroma adapters, complete selected populations | Complex layouts, semantic interpretation and arbitrary language are not universally reliable |
| Exact supported calculations | Decimal tools, operand evidence, missing/absent/zero distinctions, continuation provenance | Correct arithmetic still depends on the intended population/units being correctly selected |
| API and conversations | Typed boundaries, source identities, revision checks, acknowledged pending choices and lifecycle | One process; no authentication/tenant isolation; chat state expires/restarts |
| Desktop application | Full-width document/chat/evidence workspace; controlled Windows workflows at three desktop widths | Evaluate readability/keyboard behavior on your setup; no new mobile redesign or universal accessibility certification |
| Local Docker deployment | Real image build, host Ollama connection, persistence, offline complete backup/isolated restore and degraded behavior verified | Verify installation on the target machine; distributed scaling/public hosting excluded |
| Windows deployment | Native use and controlled Windows/browser verification; current runtime exercised through Docker | Follow the clean-folder setup guide and verify its fixed expected answers on your own machine |
| Operational validation | Focused actual-model positive/negative answers and honest fallback observed; recovery exercised | Representative business documents, dependable memory attribution and agreed operating envelope remain conditional |

The [verification record](validation.md) separates controlled test substitutes from actual-model and container evidence.

## Finite acceptance examples

**Table ACC-02 — Required bounded outcomes for a clean installation.**

| Outcome | Required behavior |
| --- | --- |
| Lookup/follow-up | North 45,000 / B2, South 38,000 / B3, in Q3 Sales |
| Calculation completeness | 124,000 with all three selected source operands, correct units and source identities |
| Missing / absent / zero | Ben's Hours missing; Zenzee absent; Asha's zero retained as an operand |
| Honest subtotal | 15.75 = 7.5 + 8.25 + 0; excluded missing B4 visible; not described as a complete total |
| Narrative identity | Orchid negation/date/page retained; Rose not replaced by Orchid; no model claim on fallback |
| Scope and context | Page aliases, explicit scope changes and counting confirmation stay within their acknowledged request |
| Document lifecycle | New chat retains documents; canceled Remove retains data; confirmed removal is selective |
| Recovery | Same source records after container recreation and isolated full-workspace restore |
| Desktop inspection | Readable answer-first layout, visible warnings, keyboard citation focus and no page-wide overflow at stated widths |

Do not turn evidence pagination or top-k retrieval into a claim that all operands were read. An answerable case refused unnecessarily is not a successful answer. An HTTP 200 or resolved citation alone is not acceptance.

## Known limitations and operating conditions

**Table ACC-03 — Remaining conditions and disposition.**

| Condition | Honest release position | Follow-up or limit |
| --- | --- | --- |
| Original model-service error | Cause unconfirmed; later Orchid calls succeeded; fallback labeled honestly | Retain as an operational finding; do not claim the retry proved its cause or removed recurrence risk |
| Narrative latency | Successful observed calls roughly 38–39 seconds on the tested laptop | No SLA/p95 claim; disclose hardware/model dependence |
| Memory and capacity | API, Ollama runner, GPU and Docker VM attribution not independently established | No universal RAM/document-size/concurrency promise; parser ceilings are protective budgets |
| Business generalization | Current accepted facts chiefly synthetic | Use an independently reviewed representative set before operational decision-making |
| Narrative understanding | Literal names/IDs and original sentence checks cover reported cases | Aliases, pronouns, multilingual/mixed subjects and full entailment remain limited |
| Desktop usability | Automated checks and focused content review exist | Evaluate readability, warnings and focus on the target desktop |
| Security/service scale | Unauthenticated loopback, one user/process, separate host model | No public service, multi-tenant isolation, high availability or horizontal scaling claim |
| Source and licensing | AGPL source/notices supplied; upstream/model terms separate | Exact corresponding source and actual bundled-component duties must be met for downstream hosting/distribution |

These conditions define the supported learning-MVP scope. Literal-subject positive/negative checks do not establish general narrative correctness. Unverified capacity and degraded model output must not be represented as successful acceptance evidence.

## Evaluate suitability for your use

Follow one clean installation route and its fixed smoke questions. Check the actual values, operands, missing-data warnings and source references. Review desktop readability and keyboard navigation. Use authorized representative documents and independently checked expected answers before relying on new workloads.

The source package does not establish a production service, hardware capacity promise or business suitability certification. Broader deployments need their own measured operating limits, security controls and acceptance evidence.
