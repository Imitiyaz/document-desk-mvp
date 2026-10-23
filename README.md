# Document Desk MVP — ask your documents, check the answer

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](AUTHORS.md).

**Keep document analysis on your own machine—and check the evidence behind the answer.**

I built Document Desk MVP to ask practical questions about Excel workbooks and PDF documents without requiring a hosted AI service. With the supplied local setup and Ollama running on the same machine, document parsing, embeddings, indexed records, calculations and model inference stay on that machine.

Local processing is only part of the goal. A useful answer also needs the right records, the right scope and a way to see what is missing. Document Desk pairs readable answers with original rows, spreadsheet cells and PDF passages. Supported calculations use exact tools over the complete selected records; narrative questions use a separate local model to select source sentences.

This is a **single-user learning MVP**, with useful working capabilities and explicit limits. It supports bounded questions and follow-ups, document removal, workspace reset and local deployment with or without Docker. It does not claim general reasoning, universal document accuracy or readiness for public multi-user hosting.

**Local processing is not an air-gap guarantee.** Installation and model downloads use external services. A remote Ollama endpoint changes where question context is sent. See [data locality and privacy](docs/privacy.md).

**Try it:** follow the [Windows native guide](docs/setup.md) or [Docker guide](docs/docker.md), upload the supplied synthetic workbook, and verify North's **45,000** against **Q3 Sales / B2**. No private business documents are needed.

Application **0.3.8** · **AGPL-3.0-only** · Local, single-user learning MVP.

[Application preview](#application-preview) · [Get started](#try-a-question-and-check-the-source) · [Capabilities](#what-you-can-do) · [Boundaries](#what-it-does-not-promise) · [All diagrams](#visual-tour) · [Lessons](#lessons-learned) · [What next](#what-next) · [Every file](PROJECT_MAP.md)

## Application preview

The desktop workspace brings the document library, question and source evidence into one view. Read the answer first, then open a citation to inspect the original cells or passages.

**Figure UI-01 — Desktop lookup with original-cell evidence expanded.**

![Document Desk MVP showing North revenue of 45,000 and its Q3 Sales B2 source](docs/assets/screenshots/desktop-lookup.png)

This is an operator-supplied application **0.3.8** screenshot using synthetic documents. It shows the interface and source-cell relationship. The model and embedding configuration was not recorded with this manual capture; the image does not establish real-model performance.

See the [UI walkthrough](docs/ui.md) for the subtotal screen, capture context and instructions to create your own screenshots.

## Start with your task


**Table OVR-T01 — Start with your task.**

| Task | Start here |
| --- | --- |
| Understand every shipped file | [Project map](PROJECT_MAP.md) and [file catalogs](docs/catalog/index.md) |
| Run without Docker on Windows | [Native setup and complete browser smoke test](docs/setup.md) |
| Run the packaged application locally | [Docker Compose deployment](docs/docker.md) |
| Understand the stack and its trade-offs | [Technology stack](docs/technology-stack.md) |
| Follow URL launch through the response | [End-to-end flow, sequence, data flow and swimlanes](docs/journey.md) |
| Understand data flow and calculations | [Architecture](ARCHITECTURE.md), [pipeline](docs/pipeline.md), [data model](docs/data-model.md) |
| Clean outputs or recover document data | [Targeted cleanup](docs/cleanup.md) and [operations/backup](docs/operations.md) |
| Preview the desktop application | [UI walkthrough](docs/ui.md) and [capture guide](docs/screenshots.md) |
| Understand local data handling | [Data locality and privacy](docs/privacy.md) |
| Browse all documentation and diagrams | [Documentation index](docs/index.md) and [all diagrams below](#visual-tour) |
| Test or contribute | [Development](docs/development.md), [testing](docs/testing.md), [contributing](CONTRIBUTING.md) |
| Review release boundaries and license | [Acceptance](docs/acceptance.md), [limitations](docs/limitations.md), [license](LICENSE-NOTICE.md) |

## What you can do

- Upload one `.pdf`, `.xlsx` or `.xlsm` file at a time; select an indexed document and ask whole-document questions.
- Retrieve supported table records with original page/sheet, row and spreadsheet-cell references.
- Calculate supported sums, minimum/maximum, increases and growth through deterministic Decimal tools. Calculations use the complete selected ledger population rather than the top-k search results.
- Request supported region/product/name breakdowns and compatible cross-section calculations; confirm physical-record counting when populations may overlap.
- Continue bounded conversations, clarify a pending request, or start a new chat without deleting documents.
- Inspect missing values, absent records, zeroes, repeated records, formula caches and disclosed Region-continuation anchors.
- Ask narrative questions using a separately installed local Ollama model. The model selects original source sentences; the application validates wording and checks explicit literal subjects.
- Remove an individual document or reset the workspace through separate confirmed actions.

## What it does not promise

- **General language understanding:** the structured planner supports a bounded set of question forms. Arbitrary analytics, fuzzy aliases, complex pronouns and open-ended agent behavior are not implemented.
- **Universal narrative correctness:** literal subject checks reduce wrong-entity substitutions; they do not prove entailment, resolve all references or guarantee a complete answer. Inspect evidence and [known limits](docs/limitations.md).
- **Arbitrary file fidelity:** no OCR for image-only PDFs, no legacy `.xls`, no arbitrary nested/malformed tables, and no execution of spreadsheet macros or recalculation of formulas.
- **Multi-user/cloud readiness:** no login, permissions, tenant isolation, distributed locking, high availability or horizontal API scaling. Run one API worker.
- **Unlimited size or speed:** parser ceilings are protective budgets, not measured capacity guarantees. Narrative latency depends on the installed model/hardware.
- **Permanent chat memory or a file archive:** conversations are process-local; temporary uploads are removed after extraction. Keep original documents in your approved source system.

## How answers are produced

**Figure OVR-01 — How answers are produced.**

```mermaid
flowchart TD
    User["`Desktop document
workspace`"] -->|"`Question and
acknowledged context`"| API["`FastAPI request
boundary`"]
    API -->|"`Resolve intent and
source scope`"| Plan{"`Supported table
operation?`"}
    Plan -->|"`Yes: read every selected
record`"| Ledger["`Complete selected
source records`"]
    Ledger -->|"`Values, units and source
locations`"| Math["`Lookup or Decimal
calculation`"]
    Plan -->|"`No: select bounded
original text`"| Search["`Narrative evidence
candidates`"]
    Search -->|"`Constrain names and
identifiers`"| Guard{"`Literal subject
supported?`"}
    Guard -->|"`Yes: select original
sentences`"| Model["`Ollama plus source
validation`"]
    Math -->|"`Result, operands and
missing status`"| Answer["`Readable answer and
expandable evidence`"]
    Model -->|"`Validated selections or
fallback`"| Answer
    Guard -->|"`No: retain requested
subject`"| Gap["No matching evidence"]
    Gap -->|"`Absence without
substitution`"| Answer
    class User interface
    class Plan,Guard decision
    class Ledger storage
    class Model model
    class Gap decision
    class Answer success
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

The decision node separates complete table operations from bounded narrative evidence. Ledger/Decimal results carry operands; the narrative subject gate can abstain before Ollama. Both paths preserve answer boundaries rather than implying general reasoning.


The table path supplies exact operands and source identities. The narrative path remains a bounded extraction workflow; neither a fluent answer nor a resolved citation establishes correctness by itself. See the [architecture explanation](ARCHITECTURE.md).

## Try a question and check the source

Follow [setup](docs/setup.md) first. Open **http://127.0.0.1:5173/** for the native development setup, or **http://127.0.0.1:8080/** for Compose. Upload `backend/tests/fixtures/sample_sales.xlsx` and ask:

> What was the Q3 revenue for North in the Q3 Sales sheet?

Expect **45,000**, with `Q3 Sales`, row **2**, cell **B2** in evidence. Then ask **And South?** and expect **38,000**, row **3**, cell **B3**. The guide also checks missing values, a subtotal and an unknown narrative subject.

## Visual tour

Every implemented-system diagram appears on this page. The [answer overview](#how-answers-are-produced) is above; the remaining views follow. Each figure links to its full explanation, component responsibilities and operating boundaries. [The compact diagram index](docs/diagrams.md) is available for direct navigation.

**Table OVR-T02 — Choose a visual reading route.**

| View | Read for |
| --- | --- |
| [Runtime and deployment](#runtime-and-deployment) | API, evidence stores, model boundary and Compose topology |
| [From browser to response](#from-browser-to-response) | URL load, optional upload, question, clarification and evidence inspection |
| [Data, processing and conversations](#data-processing-and-conversations) | Extraction, complete calculation operands, narrative routing and context |
| [Document lifecycle and responsibilities](#document-lifecycle-and-responsibilities) | Source identity, states, removal handoffs and interrupted-write recovery |
| [Security and engineering lifecycle](#security-and-engineering-lifecycle) | Trust boundaries, development checks and human release approval |

### Runtime and deployment

**Figure ARC-01 — Runtime architecture and evidence paths.**

```mermaid
flowchart TD
    Browser["`Desktop browser
React UI / API client`"] -->|"HTTP requests"| Routes["`FastAPI routes
and schemas`"]
    Routes -->|"Validated input"| Service["`PipelineService
one process / lock`"]
    Service -->|"Chat context"| State["`ConversationBook
in-memory state`"]
    Service -->|"Index upload"| Ingest["`Load / clean
chunk / embed`"]
    Service -->|"Table intent"| Tables["`Structured planner
Decimal operations`"]
    Service -->|"Text intent"| Narrative["`Retriever
narrative selector`"]
    Ingest -->|"Facts / state"| Ledger["`SQLite
source ledger`"]
    Ingest -->|"Index chunks"| Vectors["`Chroma
vector index`"]
    Ledger -->|"All selected rows"| Tables
    Ledger -->|"Source passages"| Narrative
    Vectors -->|"Ranked candidates"| Narrative
    Narrative -->|"Select sentences"| Ollama["`Ollama HTTP adapter
separate host service`"]
    Tables -->|"Result / operands"| Presenter["`Readable answer
citations / provenance`"]
    Narrative -->|"Quotes / fallback"| Presenter
    Presenter -->|"Response / evidence"| BrowserResult["Browser: inspect result"]
    class Browser,BrowserResult interface
    class Ledger,Vectors storage
    class Ollama model
    class Presenter success
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

[Architecture: components, boundaries and evidence paths](ARCHITECTURE.md#runtime-components-and-evidence-paths).

**Figure DCK-01 — Container topology and data ownership.**

```mermaid
flowchart TD
    Browser["`Desktop browser on
127.0.0.1:8080`"] -->|"`GET UI; same-origin
requests`"| Web["`NGINX and built React
files`"]
    Web -->|"Forward /api internally"| API["FastAPI: one worker"]
    API -->|"`Read / write SQLite and
Chroma`"| Workspace["Named workspace volume"]
    API -->|"Load / cache BGE weights"| Cache["`Named embedding-cache
volume`"]
    API -->|"`POST text to host Ollama
:11434`"| Ollama["Host Ollama service"]
    Ollama -->|"`Load generation-model
weights`"| Weights["Host model store"]
    class Browser,Web interface
    class Workspace,Cache,Weights storage
    class Ollama model
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

[Read the full explanation](docs/docker.md#container-topology) · [Back to visual routes](#visual-tour)

### From browser to response

**Figure E2E-01 — From application URL to readable result and source inspection.**

```mermaid
flowchart TD
    URL["`User opens application
URL`"] -->|"GET UI assets"| Web["`Vite or NGINX serves
React`"]
    Web -->|"`Initialize UI`"| Init["`Load documents,
capabilities and
workspace revision`"]
    Init -->|"`Check ready sources`"| Available{"`Source
ready?`"}
    Available -->|"`No: upload`"| Upload["`Upload and synchronous
indexing`"]
    Upload -->|"`Ready; refresh`"| Select["`Select document and
enter question`"]
    Upload -->|"`Rejected / failed`"| Error["`Show error and preserve
existing data`"]
    Available -->|"`Yes: select`"| Select
    Select -->|"`Question / context`"| API["`Validate, resolve scope
and execute request`"]
    API -->|"`Result / evidence`"| Status{"`Outcome?`"}
    Status -->|"`Answer / partial /
evidence only`"| Read["`Read result and visible
warnings`"]
    Status -->|"Needs clarification"| Clarify["`Review specific pending
choice`"]
    Clarify -->|"`Choice / context`"| API
    Status -->|"No matching evidence"| Gap["`Explain missing subject
or records`"]
    Status -->|"HTTP / transport error"| Error
    Read -->|"`Open citation or
evidence`"| Evidence["`Inspect source records,
cells and operands`"]
    Evidence -->|"`Follow-up`"| Select
    Gap -->|"`Revise subject`"| Select
    Error -->|"`Resolve; retry`"| Select
    class URL,Web,Select,Read,Evidence interface
    class Available,Status,Clarify decision
    class Error error
    class Gap decision
    class Upload storage
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

[Read the full explanation](docs/journey.md#browser-to-answer-process-flow) · [Back to visual routes](#visual-tour)

**Figure E2E-02 — URL load, optional indexing and a first or follow-up question.**

```mermaid
sequenceDiagram
    participant B as Browser
    participant W as Web
    participant A as API
    participant S as Stores
    participant M as Ollama
    rect rgb(204, 251, 241)
        Note over B,A: Load the application and workspace
        B->>W: GET /
        W-->>B: HTML / JS / CSS / license
        par Workspace metadata
            B->>W: /documents + /workspace
            W->>A: Forward both requests
            A->>S: Read ready IDs + revision
            S-->>A: Catalog + revision
            A-->>W: JSON metadata
            W-->>B: Populate source library
        and Supported formats
            B->>W: GET /api/capabilities
            W->>A: Forward /capabilities
            A-->>W: Formats + upload budget
            W-->>B: Enable upload controls
        end
    end
    rect rgb(219, 234, 254)
        Note over B,A: Index only when needed
        opt No ready document selected yet
            B->>W: POST file + revision
            W->>A: Bounded multipart upload
            A->>A: Parse / chunk / embed
            A->>S: Write facts/vectors, ready
            S-->>A: Source ID + records
            A-->>W: 201 facts or typed error
            W-->>B: Feedback, refresh catalog
        end
    end
    rect rgb(254, 243, 199)
        Note over B,A: Create a source-bound conversation
        opt First question in a chat
            B->>W: POST /api/conversations
            W->>A: Check ID + revision
            A->>A: Create bounded chat
            A-->>W: conversation_id
            W-->>B: Bind chat to source
        end
    end
    rect rgb(254, 243, 199)
        Note over B,A: Resolve the question and context
        B->>W: POST /api/query
        W->>A: Keep question + choices
        A->>A: Resolve request + context
    end
    alt Clarification or unsupported request
        rect rgb(254, 243, 199)
            A->>A: Retain constraints, ask
        end
    else Supported table request
        rect rgb(219, 234, 254)
            A->>S: All records + locations
            S-->>A: Values / gaps / units
            A->>A: Exact result / gaps
        end
    else Bounded narrative request
        rect rgb(237, 233, 254)
            A->>S: Rank + canonical passages
            S-->>A: Text + source locations
            alt Requested literal subject is absent
                A->>A: Absent: no substitution
            else Subject constraint has supporting text
                A->>M: Select original sentences
                M-->>A: Choices / model failure
                A->>A: Validate, label fallback
            end
        end
    end
    rect rgb(220, 252, 231)
        Note over B,A: Read the result and inspect its source
        A-->>W: Result / evidence / token
        W-->>B: Answer before evidence
        B->>B: Focus source citation
    end
```

[Read the full explanation](docs/journey.md#browser-to-answer-sequence) · [Back to visual routes](#visual-tour)

### Data, processing and conversations

**Figure FLOW-01 — Evidence data from upload bytes to an inspectable answer.**

```mermaid
flowchart TD
    File["Local PDF or Excel file"] -->|"`Multipart bytes and
filename`"| Parse["`Budgeted extraction and
interpretation`"]
    Parse -->|"`Rows, text, locations
and policy`"| Ledger["SQLite source ledger"]
    Parse -->|"`Cleaned chunks with
citations`"| Encode["BGE embedding adapter"]
    Encode -->|"`Vectors, text and
metadata`"| Vectors["Chroma index"]
    Query["`Question and
acknowledged
constraints`"] -->|"`Metric, scope and
population`"| Tables["`Structured selection
and Decimal tools`"]
    Ledger -->|"`All selected operands
and gaps`"| Tables
    Query -->|"`Text request and subject
constraints`"| Narrative["`Bounded narrative
evidence selection`"]
    Vectors -->|"`Ranked source-scoped
chunks`"| Narrative
    Ledger -->|"`Original canonical
passages`"| Narrative
    Narrative -->|"`Matching text; select
sentences`"| Model["Configured Ollama model"]
    Model -->|"`Candidate sentence
choices`"| Validate["`Source quotation and
subject checks`"]
    Narrative -->|"`Passages, gap or
fallback status`"| Validate
    Tables -->|"`Exact result, operands
and sources`"| Output["`Response JSON and
browser evidence`"]
    Validate -->|"`Valid text / excerpts /
absence`"| Output
    class File,Query,Output interface
    class Ledger,Vectors storage
    class Model model
    class Validate decision
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

[Read the full explanation](docs/journey.md#data-flow-and-retention) · [Back to visual routes](#visual-tour)

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

[Read the full explanation](docs/pipeline.md#ingestion) · [Back to visual routes](#visual-tour)

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

[Read the full explanation](docs/pipeline.md#query-routing) · [Back to visual routes](#visual-tour)

**Figure API-01 — Conversations.**

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Session
    participant Ledger
    rect rgb(204, 251, 241)
        Note over Client,API: Open a document-bound chat
        Client->>API: Start chat: source + revision
        API->>Ledger: Check ready source ID
        API->>Session: Create bound conversation
        API-->>Client: conversation_id
    end
    rect rgb(254, 243, 199)
        Note over Client,Session: Resolve the acknowledged request
        Client->>API: Question + context
        API->>Session: Resolve pending choices
    end
    rect rgb(219, 234, 254)
        Note over API,Ledger: Read the complete selected population
        API->>Ledger: Read complete records
    end
    rect rgb(220, 252, 231)
        Note over Client,API: Return result and source evidence
        API-->>Client: Answer / evidence / token
    end
```

[Read the full explanation](docs/api.md#conversations) · [Back to visual routes](#visual-tour)

### Document lifecycle and responsibilities

**Figure DATA-01 — Source ledger.**

```mermaid
erDiagram
    DOCUMENTS ||--|| DOCUMENT_STATE : "source identity"
    DOCUMENTS {
        text source PK
        text version
        text digest
        text payload
    }
    DOCUMENT_STATE {
        text source PK
        text document_id
        text state
        text profile
    }
    WORKSPACE {
        integer id PK
        integer revision
    }
    PIPELINE_META {
        text key PK
        text value
    }
    classDef content fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A
    classDef lifecycle fill:#FEF3C7,stroke:#B45309,color:#78350F
    classDef workspace fill:#CCFBF1,stroke:#0F766E,color:#134E4A
    classDef metadata fill:#F1F5F9,stroke:#64748B,color:#0F172A
    class DOCUMENTS content
    class DOCUMENT_STATE lifecycle
    class WORKSPACE workspace
    class PIPELINE_META metadata
```

[Read the full explanation](docs/data-model.md#source-ledger) · [Back to visual routes](#visual-tour)

**Figure DATA-02 — Document state.**

```mermaid
stateDiagram-v2
    [*] --> Extracting: upload accepted
    Extracting --> Indexing: usable chunks and embeddings
    Extracting --> Rejected: parsing or budget failure
    Indexing --> Ready: ledger and vectors written
    Indexing --> Deleting: write failed
    Ready --> Deleting: remove or reset
    Deleting --> Removed: cleanup succeeds
    Deleting --> Deleting: cleanup pending
    Removed --> [*]: source no longer indexed
    Rejected --> [*]: no usable source published
    classDef processing fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A
    classDef ready fill:#DCFCE7,stroke:#15803D,color:#14532D
    classDef rejected fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D
    classDef cleanup fill:#FEF3C7,stroke:#B45309,color:#78350F
    classDef removed fill:#F1F5F9,stroke:#64748B,color:#0F172A
    class Extracting,Indexing processing
    class Ready ready
    class Rejected rejected
    class Deleting cleanup
    class Removed removed
```

[Read the full explanation](docs/data-model.md#document-state) · [Back to visual routes](#visual-tour)

**Figure SWIM-01 — Browser, API and persistence responsibilities across a document lifecycle.**

```mermaid
flowchart TD
    subgraph UI["Browser lane"]
        direction LR
        Pick["Choose file"]
        Indexed["`View current document
catalog`"]
        Remove["`Confirm selected
document removal`"]
    end
    subgraph Service["API lane"]
        direction LR
        Ingest["`Validate, parse and
embed under lock`"]
        Identity["`Check selected document
version`"]
        Cleanup["`Delete only selected
source data`"]
    end
    subgraph Data["Persistence lane"]
        direction LR
        Write["`Store indexing ledger
and vector batch`"]
        Ready["Publish ready source"]
        Delete["`Mark deleting, then
remove source payload`"]
    end
    Pick -->|"`POST bytes and expected
revision`"| Ingest
    Ingest -->|"`Write facts, locations
and vectors`"| Write
    Write -->|"Both stores complete"| Ready
    Ready -->|"201; refresh catalog"| Indexed
    Indexed -->|"Request Remove; confirm"| Remove
    Remove -->|"`DELETE current
document_id`"| Identity
    Identity -->|"Current identity matches"| Cleanup
    Cleanup -->|"`Mark deleting; remove
vectors`"| Delete
    Delete -->|"`200; refresh source
catalog`"| Indexed
    class Pick,Indexed,Remove interface
    class Identity decision
    class Write,Delete storage
    class Ready success
    style UI fill:#F0FDFA,stroke:#0F766E,color:#134E4A
    style Service fill:#F8FAFC,stroke:#64748B,color:#0F172A
    style Data fill:#EFF6FF,stroke:#2563EB,color:#1E3A8A
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

[Read the full explanation](docs/journey.md#swimlane-responsibilities-for-indexing-and-removal) · [Back to visual routes](#visual-tour)

**Figure OPS-01 — Startup reconciliation of incomplete document writes.**

```mermaid
flowchart TD
    Start["API startup"] -->|"`Read lifecycle`"| Inspect["Read pending sources"]
    Inspect -->|"Next incomplete source"| Pending{"`Pending
source?`"}
    Pending -->|"`Yes: compensate`"| Delete["`Delete source vectors
and ledger payload`"]
    Delete -->|"`Check cleanup`"| Success{"`Cleaned?`"}
    Success -->|"`Yes: next source`"| Inspect
    Success -->|"`No: retain state`"| Unavailable["`Keep affected source
unavailable`"]
    Pending -->|"`No: ready catalog`"| Serve["Serve ready catalog"]
    Unavailable -->|"Exclude affected source"| Serve
    class Pending,Success decision
    class Unavailable error
    class Serve success
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

[Read the full explanation](docs/operations.md#interrupted-indexingdeletion) · [Back to visual routes](#visual-tour)

### Security and engineering lifecycle

**Figure SEC-01 — Local trust and data-transfer boundaries.**

```mermaid
flowchart TD
    Files["`Untrusted document
bytes and text`"] -->|"`File and extraction
budgets`"| Parsers["`Document parsing and
interpretation`"]
    User["Local browser"] -->|"`Unauthenticated loopback
HTTP`"| API["`Application service
boundary`"]
    Parsers -->|"`Facts and original
locations`"| API
    API -->|"`Read / persist document
content`"| Storage["`Local ledger and
vectors`"]
    API -->|"`Bounded passages for
selection`"| Endpoint["`Configured Ollama
endpoint`"]
    Packages["`Package and model
registries`"] -->|"`Install / first-use
download`"| Runtime["`Dependencies and model
cache`"]
    Runtime -->|"`Parser and embedding
code`"| Parsers
    Runtime -->|"`Separately licensed
weights`"| Endpoint
    class User interface
    class Storage,Runtime storage
    class Endpoint model
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

[Read the full explanation](SECURITY.md#supported-boundary) · [Back to visual routes](#visual-tour)

**Figure LIFE-01 — Engineering decision gates and release ownership.**

```mermaid
flowchart TD
    Need["`Outcome and acceptance
contract`"] -->|"`Agree scope and
exclusions`"| Design["`Design, threats and
data changes`"]
    Design -->|"`Approve contracts and
rollback`"| Branch["`Focused implementation
branch`"]
    Branch -->|"`Implementation and
expectations`"| Verify["Tests and code review"]
    Verify -->|"Review results and risks"| Gate{"`Enough
evidence?`"}
    Gate -->|"`No: bound corrective
work`"| Design
    Gate -->|"Yes: present conditions"| Approval["`Maintainer release
approval`"]
    Approval -->|"`Record acceptance
conditions`"| Release["`Versioned source and
checksums`"]
    Release -->|"Install reviewed version"| Operate["`Observe, recover and
manage retention`"]
    Operate -->|"`New requirements or
incidents`"| Need
    class Gate decision
    class Approval,Release success
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

[Read the full explanation](docs/development.md#roles-and-decision-gates) · [Back to visual routes](#visual-tour)

**Figure LIFE-02 — Implemented CI checks and manual release decision.**

```mermaid
flowchart TD
    Event["`Pull request, main push
or manual run`"] -->|"`Check source and
documentation`"| Repo["`Repository and catalog
guards`"]
    Event -->|"Isolated Python matrix"| Backend["`Backend tests and
quality checks`"]
    Event -->|"`Node build and component
checks`"| Frontend["`Types, React tests,
audit and build`"]
    Event -->|"Isolated browser servers"| Browser["`Controlled browser
workflows`"]
    Event -->|"`Compose; build on manual
dispatch`"| Docker["`Container configuration
and optional image
build`"]
    Repo -->|"`Catalog, links and
boundaries`"| Review["`Maintainer reviews all
results`"]
    Backend -->|"`Tests and static
analysis`"| Review
    Frontend -->|"`Rendering, typing and
build`"| Review
    Browser -->|"`Actual requests and
evidence`"| Compare["`Independent
expectations and
viewport comparison`"]
    Compare -->|"`Compare values, sources,
status`"| Review
    Docker -->|"`Config / build, not
model proof`"| Review
    Review -->|"`Acceptance and license
gates`"| Decision["`Approve, revise or
reject`"]
    class Browser interface
    class Decision decision
    classDef default fill:#F1F5F9,stroke:#64748B,color:#0F172A,font-size:15px,stroke-width:1.3px
    classDef success fill:#DCFCE7,stroke:#15803D,color:#14532D,font-size:15px
    classDef error fill:#FEE2E2,stroke:#B91C1C,color:#7F1D1D,font-size:15px
    classDef decision fill:#FEF3C7,stroke:#B45309,color:#78350F,font-size:14px
    classDef model fill:#EDE9FE,stroke:#7C3AED,color:#4C1D95,font-size:15px
    classDef storage fill:#DBEAFE,stroke:#2563EB,color:#1E3A8A,font-size:15px
    classDef interface fill:#CCFBF1,stroke:#0F766E,color:#134E4A,font-size:15px
    linkStyle default font-size:12px,color:#334155
```

[Read the full explanation](docs/development.md#ci-implemented-in-this-repository) · [Back to visual routes](#visual-tour)

## Lessons learned

- **Plan the outcome before generating code.** Define supported questions, exclusions and expected source facts; a narrow contract makes it easier to review a change.
- **Budget for AI-assisted development.** Allow for monthly tool subscriptions and usage even when learning, and remember that mistakes consume time as well as tokens. Requirements, testing, integration and documentation still need attention.
- **Keep decisions and handovers portable.** Clear contracts, reproducible fixtures and written evidence helped me continue the work across Anthropic Claude and OpenAI ChatGPT/Codex.
- **Check the population, not only the arithmetic.** A correct sum over omitted or misidentified rows is still the wrong answer. A citation can also point to the wrong subject.
- **Test the conversation and the tools that test it.** Follow-ups, page changes, missing values, failed model calls and browser controls need independent expectations.
- **Make recovery part of the application.** A usable local workspace needs deliberate deletion, persistence, backup and restore, as well as a successful first upload.

These are lessons from building this MVP, not claims that every failure class has been eliminated. See [verification scope](docs/validation.md) and [known limitations](docs/limitations.md).

## What next

This MVP gives me a foundation for a broader **Document Intelligence Workspace**: a place to explore documents conversationally, inspect their evidence and perform supported analysis while keeping local processing a central design goal.

That larger workspace is a direction for future work, not an implemented capability claim. Better intent understanding, representative document evaluation, measured resource limits and richer workflows need their own design and evidence.

I would welcome like-minded developers who want to improve document extraction, evaluation, accessibility, reproducibility or the local user experience. Start with [Contributing](CONTRIBUTING.md), propose a bounded problem and bring a synthetic example with an independently checked answer. The application is AGPL-3.0-only; model and dependency terms remain separate.

## Release scope and verification

This first public-source release packages application **0.3.8**. Controlled regression, Windows browser, local Docker recovery and focused actual-model checks cover the documented cases. The [verification record](docs/validation.md) distinguishes those layers; it is not an independent certification.

Narrative latency, representative business-document coverage, reliable memory attribution and a measured capacity envelope remain limitations. Read the [supported scope](docs/acceptance.md) before adopting a new workload.

## License and attribution

Copyright © 2026 **Imitiyaz**, author and project owner. AI development and verification support is credited in [Authors and attribution](AUTHORS.md). The application is licensed under [GNU AGPL v3 only](LICENSE); commercial use is permitted under its conditions. Read [source availability](LICENSE-NOTICE.md) and [third-party notices](THIRD_PARTY_NOTICES.md). Models and dependencies retain their own licenses. Built with Llama when using the configured Llama 3.1 model.
