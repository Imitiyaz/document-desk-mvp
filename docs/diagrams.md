# Diagram index and visual conventions

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

Every figure appears in the [README visual tour](../README.md#visual-tour), including the [answer overview](../README.md#how-answers-are-produced). The table links each figure to its detailed implementation context.

**Table DIA-01 — Figure references and detailed explanations.**

| Figure | Subject | Detailed explanation |
| --- | --- | --- |
| ARC-01 | Runtime architecture and evidence paths | [Read context](../ARCHITECTURE.md#runtime-components-and-evidence-paths) |
| OVR-01 | How answers are produced | [Read context](../README.md#how-answers-are-produced) |
| SEC-01 | Local trust and data-transfer boundaries | [Read context](../SECURITY.md#supported-boundary) |
| API-01 | Conversations | [Read context](../docs/api.md#conversations) |
| DATA-01 | Source ledger | [Read context](../docs/data-model.md#source-ledger) |
| DATA-02 | Document state | [Read context](../docs/data-model.md#document-state) |
| LIFE-01 | Engineering decision gates and release ownership | [Read context](../docs/development.md#roles-and-decision-gates) |
| LIFE-02 | Implemented CI checks and manual release decision | [Read context](../docs/development.md#ci-implemented-in-this-repository) |
| DCK-01 | Container topology and data ownership | [Read context](../docs/docker.md#container-topology) |
| OPS-01 | Startup reconciliation of incomplete document writes | [Read context](../docs/operations.md#interrupted-indexingdeletion) |
| PIPE-01 | Ingestion from bounded upload to ready document | [Read context](../docs/pipeline.md#ingestion) |
| PIPE-02 | Query routing, clarification and honest fallback | [Read context](../docs/pipeline.md#query-routing) |
| E2E-01 | From application URL to readable result and source inspection | [Read context](../docs/journey.md#browser-to-answer-process-flow) |
| E2E-02 | URL load, optional indexing and a first or follow-up question | [Read context](../docs/journey.md#browser-to-answer-sequence) |
| FLOW-01 | Evidence data from upload bytes to an inspectable answer | [Read context](../docs/journey.md#data-flow-and-retention) |
| SWIM-01 | Browser, API and persistence responsibilities across a document lifecycle | [Read context](../docs/journey.md#swimlane-responsibilities-for-indexing-and-removal) |

## Visual conventions

The palette has the same meaning across architecture, flow, sequence, ER and state views. Sequence diagrams use colored phase bands; ER diagrams color entity roles; state diagrams color lifecycle outcomes. The notation remains appropriate to each diagram type.

**Table DIA-02 — Shared semantic colors.**

| Color | Fill / border | Meaning |
| --- | --- | --- |
| Slate | #F1F5F9 / #64748B | Processing, coordination or neutral metadata |
| Teal | #CCFBF1 / #0F766E | Browser, interface or workspace boundary |
| Blue | #DBEAFE / #2563EB | Source data, storage and indexing |
| Violet | #EDE9FE / #7C3AED | Model-assisted processing |
| Amber | #FEF3C7 / #B45309 | Decision, pending clarification, missing evidence or cleanup |
| Green | #DCFCE7 / #15803D | Ready state or returned result; not a universal correctness guarantee |
| Red | #FEE2E2 / #B91C1C | Rejection or operational failure |

Labels carry the meaning as well as color. Small decision diamonds ask short questions. Detailed conditions belong on the branches or in adjacent explanations. Flowchart component text is primary; connector captions use a smaller font where the Mermaid renderer supports edge styling. Sequence/ER/state renderers retain their own text rules.

## Editing and rendering

The Mermaid block in each linked context page is the authoritative source; README mirrors it exactly. OVR-01 is authored directly in README. Update both copies when changing another figure, then run:

```powershell
python .\tools\check_repository.py
python .\tools\catalog.py --check
```

Keep decision text short, wrap captions intentionally and retain branch conditions. Use layout and routing to resolve overlaps rather than shrinking everything. Do not add invisible layout arrows that look like runtime behavior.

GitHub and editor integrations can use different Mermaid versions and defaults. Inspect the actual rendering at normal reading width, including the dense end-to-end sequence. Parse success alone is not visual approval. See [Mermaid flowcharts](https://mermaid.js.org/syntax/flowchart.html), [sequence phase bands](https://mermaid.js.org/syntax/sequenceDiagram.html), [ER styling](https://mermaid.js.org/syntax/entityRelationshipDiagram.html), [state styling](https://mermaid.js.org/syntax/stateDiagram.html) and [GitHub diagrams](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/creating-diagrams).

These are implementation diagrams, not certification of correctness, security or measured capacity.
