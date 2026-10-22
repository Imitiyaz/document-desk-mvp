# Verification scope and known limits

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## How to read the evidence

I evaluate this MVP at several layers: isolated backend behavior, rendered components, browser requests, container persistence/recovery and focused actual-model questions. Each layer answers a different question. A passing HTTP status, citation marker or coverage percentage does not establish factual correctness.

The results below are bounded observations for application **0.3.8**, obtained across the named layers. They are not one simultaneous run or a performance guarantee. Resource-marked tests and substituted model/vector adapters must remain explicit when reproducing a check.

## Runtime and deployment observations

**Table VAL-01 — Evidence layers and their boundaries.**

| Layer | Observed result | Boundary |
| --- | --- | --- |
| Backend regression | 704 selected tests passed; 26 resource-marked cases excluded | Lightweight injected resources do not establish real-model capacity |
| Frontend components | 62 tests passed across seven files | DOM/component checks are not full-browser accessibility proof |
| UI/capture checkers | 46 cases passed | Check independent expected values, source identities and unsuccessful-response recording |
| Windows browser | Eight interaction workflows and three desktop-width workflows passed in separate batches | Combined observations, not a new single eleven-case run |
| Windows Docker | Seven deployment scenarios passed | Local single-worker Compose; no multi-user or horizontal-scale claim |
| Actual-model narrative | Orchid: not approved; review 2026-11-03; page 4 source | Focused synthetic question, not arbitrary semantic accuracy |
| Absent literal subject | Rose: no matching evidence; no Orchid facts/citation | Does not establish alias/pronoun resolution |

Docker checks covered lookup/cell identity, persistence after recreation, persisted provenance, complete offline workspace backup, isolated restore, unavailable-model fallback and selective cleanup.

## Independently checked examples

**Table VAL-02 — Expected values and source requirements.**

| Scenario | Required result |
| --- | --- |
| North lookup | 45,000; Q3 Sales row 2, B2 |
| Three-region sum | 45,000 + 38,000 + 41,000 = 124,000, with every operand |
| Hours subtotal | 7.5 + 8.25 + 0 = 15.75; missing B4 disclosed/excluded; recorded zero retained |
| PDF page totals | Page 1: 10 + 6 = 16; page 3: 4 + 8 = 12; confirmed physical-record total 28 |
| Narrative identity | Orchid's negation/date stay with Orchid; Rose is not substituted |

These cases establish the supplied fixtures and tested workflows. Representative business documents need independently reviewed expectations before operational use.

## Documentation and visual checks

Repository checks cover links, titles/captions, human/AI attribution, decision ownership, identical README/context diagram sources and an exhaustive file inventory. Mermaid parsing checks syntax; rendered inspection checks presentation. Neither establishes application correctness.

The [UI walkthrough](ui.md) identifies the mode behind each shipped screenshot. Controlled browser captures demonstrate the interface using test adapters; they are not evidence of real-model latency. Reproduce captures using [the screenshot guide](screenshots.md).

See [testing](testing.md) for exact runtime commands and [diagram maintenance](diagrams.md#editing-and-rendering) for figure checks. AI-assisted summaries are not independent certification.

## Operating limits

Successful actual-model narrative calls were observed at roughly **38–39 seconds** on the tested laptop. Model-service unavailability can return explicitly labeled evidence-only fallback. An observed connection failure has no confirmed root cause; no recurrence rate or p95 latency is established.

Reliable API/Ollama/GPU/VM memory attribution, representative document coverage and a measured capacity envelope are not established. Parser ceilings are protective budgets. The application uses a local, single-user, unauthenticated boundary. Read [limitations](limitations.md), [security](../SECURITY.md) and [supported scope](acceptance.md).
