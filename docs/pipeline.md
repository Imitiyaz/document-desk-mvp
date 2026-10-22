# Processing and answer flow

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## Ingestion

**Figure PIPE-01 — Ingestion from bounded upload to ready document.**

```mermaid
flowchart TD
    Upload["`Upload filename
bounded bytes`"] -->|"Type / name"| Dispatch{"Loader?"}
    Dispatch -->|"Unsupported / legacy"| Reject["Typed HTTP rejection"]
    Dispatch -->|"Supported; apply budgets"| Extract["`Extract cells / tables
text / locations`"]
    Extract -->|"Raw facts"| Clean["`Normalize
deduplicate`"]
    Clean -->|"Physical provenance"| Chunk["`Citation-bearing
row / prose chunks`"]
    Chunk -->|"Encode chunks"| Embed["BGE embeddings"]
    Embed -->|"Complete batch"| Indexing["`Write source ledger
as indexing`"]
    Indexing -->|"Upsert source batch"| Vectors["Write Chroma vectors"]
    Vectors -->|"All chunks persisted"| Ready["`Mark ready
return HTTP 201`"]
    Vectors -->|"Write / count failure"| Cleanup["`Mark deleting
compensate`"]
    Cleanup -->|"Cleaned or unavailable"| Removed["`Typed failure
recovery state`"]
    class Dispatch decision
    class Reject,Removed error
    class Embed model
    class Indexing,Vectors storage
    class Ready success
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

Type dispatch and budgets precede extraction. Cleaned physical source identities flow into chunks and embeddings. Indexing is not ready until both stores are written; failures enter compensating deletion. This is lifecycle coordination, not a shared SQLite/Chroma transaction.


The loader registry discovers supported suffixes. XLSX/XLSM extraction preserves sheet names, Excel row/cell coordinates, physical values, merged anchors, formats and formula-cache diagnostics. Legacy XLS is rejected with conversion guidance. Formula expressions and workbook macros are not executed.

PDF extraction combines PyMuPDF text access and pdfplumber tables. Source locations are page names such as `page_1`, table-row identifiers such as `table_1_row_1` and text locations such as `full_page_text`. These are extraction locations, not bounding-box annotations or OCR verification.

Cleaning normalizes cells/text, removes qualifying repeated headers/footers and deduplicates table text where supported. Heuristics are tested against synthetic cases and can still misinterpret complex layouts.

Row chunks carry column labels and source identity. Wide rows may create several fragments; the ledger keeps the original complete physical row for structured operations. Prose chunking uses a text splitter while retaining page/location metadata.

## Query routing

**Figure PIPE-02 — Query routing, clarification and honest fallback.**

```mermaid
flowchart TD
    Request["`Question and
acknowledged context`"] -->|"`Check identity`"| Validate["Resolve current request"]
    Validate -->|"`Check scope`"| Clarify{"`Clarify?`"}
    Clarify -->|"`Yes: retain context`"| Choice["`Return actionable
choice or explicit gap`"]
    Clarify -->|"`No: route`"| Structured{"`Table
request?`"}
    Structured -->|"`Yes: select rows`"| Population["`Read full source-ledger
population`"]
    Population -->|"`Units / gaps / basis`"| Calculation["`Lookup or exact
operation`"]
    Calculation -->|"`Operands / evidence`"| Present["`Readable result,
warnings and evidence`"]
    Structured -->|"`No: retrieve`"| Retrieve["`Ranked chunks and
original passages`"]
    Retrieve -->|"`Keep subject`"| Subject{"`Subject
found?`"}
    Subject -->|"`No: abstain`"| Absent["No matching evidence"]
    Subject -->|"`Yes: source text`"| Model["`Ollama sentence
selection`"]
    Model -->|"`Validate output`"| Check{"`Selection
outcome?`"}
    Check -->|"`Valid quotes`"| Present
    Check -->|"Valid empty selection"| Absent
    Check -->|"`Invalid / failed`"| Excerpts["`Labeled bounded source
excerpts`"]
    Excerpts -->|"`Label fallback`"| Present
    class Clarify,Choice,Structured,Subject,Check decision
    class Present success
    class Absent decision
    class Population storage
    class Model model
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

Acknowledged conversation/source checks happen before planning. Supported calculations select a full ledger population. Narrative requests pass through bounded retrieval, explicit-subject checks, model selection and original-sentence validation. Missing subjects abstain; invalid synthesis becomes labeled excerpts rather than an answered claim.


The narrative branch first constrains literal names/IDs and supported simple subject phrases to matching source text. It never treats Orchid as an alias for Rose. A model selecting no claims produces no evidence, rather than an answered card containing fallback excerpts. Invalid nonempty selections produce labeled excerpts from the constrained passages. This remains a bounded guard, not general entity linking or entailment.

The structured path supports recognized lookups, sums, extrema and comparisons. Unknown natural-language qualifiers may require clarification. Supplying schema-valid fields does not guarantee the intended business interpretation.

## Interpretation rules

Merged-cell values carry their physical anchor. Separately, the implemented `region-continuation-v1` policy can interpret an adjacent blank **Region** cell as a continuation when its conditions are met. This is an explicit domain assumption, not a universal spreadsheet rule. The original blank, original cell and inherited anchor remain in evidence.

Totals distinguish:

- **Complete selected total:** all selected numeric values are available under the chosen population.
- **Available-value subtotal:** known numeric values are summed and missing cells remain unknown.
- **No matching records:** no zero or fabricated contribution is inferred.
- **Ambiguous population:** overlapping/unknown cross-sheet populations require clarification.

Formatting uses original types/strings to preserve identifiers, signs, decimals and date literals. Calculation validation checks units and source associations; it does not perform currency conversion or invent missing values.

## Failure and recovery

Unsupported type, corrupt input, extraction budget, duplicate name and stale workspace errors have distinct codes. Temporary upload files are removed after the request. An indexing failure attempts source-scoped cleanup. If cleanup fails, the document remains unavailable and is reconsidered on startup.

The outer request body budget and file budget are distinct. Large bodies can fail before the parser is called. See [API](api.md) for statuses and [operations](operations.md) for recovery.
