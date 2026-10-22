# Browser-to-answer journey — flow, sequence, data and responsibilities

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

These diagrams begin **after the operator has started the services** using [native setup](setup.md) or [Docker](docker.md). Typing a URL does not launch Python, Docker or Ollama. They explain an actual user's journey through this implementation, not a proposed autonomous-agent system.

## Browser-to-answer process flow

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

The web layer is Vite on native port 5173 or NGINX on Compose port 8080. React first loads catalog, capability and workspace-revision metadata; it does not begin by sending a question to the model. Upload is optional when a ready source already exists. A normal HTTP response may contain an answer, a subtotal, a clarification, evidence-only fallback or no matching evidence; the UI renders those differences. A citation action opens evidence already supplied in that response instead of asking the model to reconstruct a source.

**Table JOURNEY-T01 — User-visible stages and implementation references.**

| Stage | What moves / what the user sees | Main implementation |
| --- | --- | --- |
| URL and application files | HTML, JavaScript, styles and legal/source link | `frontend/index.html`, Vite config or `deploy/nginx.conf` |
| Workspace initialization | Catalog, supported extensions, upload limit and workspace revision | `frontend/src/App.tsx`, `api.ts`, API catalog/capability/workspace routes |
| Optional upload | Bounded multipart bytes; indexed/ready feedback | Upload route, loader registry and `PipelineService.ingest` |
| Question and chat context | Selected document ID, question, acknowledged token and optional refinements | UI query method, schemas and `ConversationBook` |
| Evidence and execution | Complete table population or bounded narrative passages | Structured engine/store, retriever and grounded generation |
| Result inspection | Readable values, status/warnings, operands and source records | `AnswerContent.tsx`, `App.tsx`, response models/presenter |

See [pipeline diagrams](pipeline.md) for detailed ingestion and routing branches; [API](api.md) for exact request/response contracts.

## Browser-to-answer sequence

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

There are five participants. The stores represent two persistence adapters, not one shared transaction; BGE embedding runs in the API process. Narrative selection may call the separate host model, while structured values/calculations do not. The web layer removes the `/api` prefix before forwarding. Existing chats skip the conversation-creation step and acknowledge the latest accepted response token. Error responses and no-evidence results are outcomes, not invented factual answers. Runtime startup/readiness is documented separately from this browser journey.

## Data flow and retention

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

This is a logical data-flow view: edge labels name the data crossing a boundary. It is not a formal security certification. SQLite retains canonical extracted payloads and interpretation provenance; Chroma retains search chunks/vectors. The raw file is used for a digest and its temporary staging copy is removed after processing. The browser may hold recent answer/history content; process-local conversation constraints are distinct from persistent document data. Neither the vector index nor a model-generated sentence is an independently checked business truth. See [data semantics](data-model.md), [trust boundaries](../SECURITY.md) and [cleanup domains](cleanup.md).

## Swimlane responsibilities for indexing and removal

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

The horizontal groups are responsibility lanes, not separate background workers. The browser requests an action and displays its outcome. The API validates identities, holds the process lock and orchestrates work. Persistence records whether a source is ready, indexing or deleting. The removal path uses the currently selected version; **New chat is not that path**. If a write/cleanup fails, compensation and startup reconciliation keep the affected source unavailable; there is no distributed transaction. The [state machine](data-model.md#document-state) shows those failure/recovery states, and [operations](operations.md#interrupted-indexingdeletion) explains recovery.

## Sequence caption details

The sequence uses short message captions to avoid forcing adjacent participants far apart. Browser means React and its API client; Web means Vite during native development or NGINX in Compose; API means the single FastAPI/service process; Stores means the SQLite/Chroma adapters; Ollama is the separate host model service. The grouping does not add a shared database transaction.

**Table JOURNEY-T06 — Full meaning of compact sequence captions.**

| Caption group | Full protocol meaning |
| --- | --- |
| Assets and library | GET / returns HTML, JavaScript, CSS and source/license assets. Concurrent metadata requests obtain ready document identities, workspace revision, supported formats and upload budget. |
| Upload | Multipart file and expected workspace revision are validated. Parsing, cleaning, chunking and local BGE embedding precede source-ledger/vector writes and ready publication. The result is a 201 source identity/count summary or typed error. |
| Bind chat | Conversation creation validates the selected document ID and workspace revision, creates bounded in-memory state and returns conversation_id. Existing chats skip creation. |
| Query and choices | The proxy forwards the exact question, acknowledged context and counting choice. The API validates identity and resolves pending constraints; clarification keeps the parts already understood. |
| Table records | Every selected record carries values, raw missing cells, units and original locations. Exact operations disclose incomplete populations and return their complete operands. |
| Narrative | Ranked chunks and canonical original passages remain bounded. Literal subject absence returns no_evidence without substitution. Otherwise the model selects original sentences; validation produces supported quotations, labeled fallback or honest empty evidence. |
| Response | Status, resolved question, evidence, warnings and next context token are returned. The UI presents a readable result before expandable details; activating a citation focuses its returned source reference. |
