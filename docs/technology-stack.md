# Technology stack, responsibilities and selection rationale

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## Evidence and decision status

This inventory describes the code/manifests in this distribution. Versions below are direct manifest pins, not a claim that every transitive package or base image is immutable. I chose these components for local processing, inspectable evidence and replaceable adapters. The decision records explain their trade-offs. NGINX serves the built frontend and proxies API requests in the Docker deployment.

## Application and model components


**Table TECHNOLOGYST-T01 — Application and model components.**

| Component | Version/source | Responsibility | Why used here | Trade-off |
| --- | --- | --- | --- | --- |
| Python | 3.12 reference setup | Backend runtime | Typed ecosystem and mature document/ML libraries | Windows/native-wheel compatibility requires testing |
| FastAPI / Starlette integration | FastAPI 0.143.0 | HTTP routes, lifespan, OpenAPI | Explicit schemas, injectable service and automatic contract documentation | Does not supply authorization or correctness guarantees |
| Pydantic / pydantic-settings | 2.14.1 / 2.15.0 | Request/config validation | Centralized typed boundaries | Valid schema is not a valid factual answer |
| Uvicorn | 0.54.0 | ASGI serving | Small explicit local server | Must use one worker because state/lock are process-local |
| React / React DOM | 18.3.1 | Document/chat/evidence UI | Familiar component/state model; strong test tooling | UI state must not outrun acknowledged server context |
| TypeScript | 5.9.3 | Frontend contracts | Catch shape errors before runtime | Runtime responses still require correct server behavior |
| Vite / React plugin | 8.3.4 / 6.1.2 | Dev proxy and static production build | Fast iteration and a simple deployable bundle | Development server is not the container production server |
| Axios | 1.20.0 | HTTP client | Existing cancellation and normalized error handling | Cancellation does not roll back work already received |
| SQLite (Python stdlib) | Python/platform supplied | Canonical source rows, raw cells and lifecycle state | Local persistence and complete population queries for exact calculations | No shared transaction with Chroma |
| Chroma | 1.5.9 | Vector persistence and similarity search | Local embedding integration with metadata filters | Similarity ranking cannot establish all aggregation operands |
| SentenceTransformers | 6.1.0 | Embedding adapter | Replaceable encoder with explicit dimension/profile checks | CPU/RAM cost and model cache/download |
| BAAI/bge-base-en-v1.5 | Model identifier, 768 dimensions | English semantic embeddings | Established local baseline retained for comparability | English-centric behavior; weights/revision must be recorded |
| Ollama | Separately installed; record actual version | Local model HTTP service | Keep model execution outside the API process | Independent availability, RAM/GPU use and licensing |
| Llama 3.1 8B instruct Q4_K_M | `llama3.1:8b-instruct-q4_K_M` | Bounded original-sentence proposal | Local quantized model for bounded sentence selection | Not universal reasoning; variable generation latency |
| Decimal | Python stdlib | Numeric operations | Avoid binary floating-point drift and model arithmetic | Units/populations still require valid interpretation |

## Parsing and supporting libraries


**Table TECHNOLOGYST-T02 — Parsing and supporting libraries.**

| Component | Direct pin | Used for | Decision rationale / boundary |
| --- | --- | --- | --- |
| openpyxl | 3.1.5 | Physical cells, merges, formulas and cached workbook values | Preserve original coordinates; never run macros or calculate formulas |
| pandas | 3.0.6 | Tabular extraction/normalization support | Familiar tabular tools; original-cell semantics remain explicit |
| PyMuPDF | 1.28.2 | PDF narrative text | Page-text extraction with page provenance; AGPL obligations documented |
| pdfplumber | 0.11.10 | PDF table regions | Complement page text with structured rows; arbitrary layouts remain unsupported |
| langchain-text-splitters | 1.1.3 | Bounded prose splitting | Bound prose length while retaining its source location |
| LangChain / community packages | 1.4.5 / 0.4.2 | Retained integration dependencies | Supporting integrations; the service is not a general autonomous LangChain agent |
| NumPy | 2.5.4 | Embedding arrays and test vectors | Standard numerical array representation |
| HTTPX / tenacity | 0.28.1 / 9.2.1 | Model HTTP transport and bounded retries | Explicit transport errors; retries do not make answers correct |
| Loguru | 0.7.3 | Structured application logs | Consistent pipeline diagnostics; logs may contain document/question content |
| python-multipart | 0.0.32 | Upload form parsing | FastAPI multipart upload support; additional application budgets still required |

## Quality and delivery components


**Table TECHNOLOGYST-T03 — Quality and delivery components.**

| Component | Responsibility | Why / limitation |
| --- | --- | --- |
| pytest, pytest-asyncio, pytest-cov | Unit, integration, HTTP and coverage reporting | Independent values/source assertions and failure cases; coverage alone is not quality |
| ReportLab | Synthetic PDF fixture generation | Reproducible known facts without private business documents |
| Ruff, Black, mypy | Lint, format and backend type checking | Complement behavioral tests; cannot establish factual correctness |
| Vitest / Testing Library / jsdom | Rendered React component checks | Fast DOM interaction checks; not full-browser visual proof |
| Playwright | Real browser workflows and screenshots | Validate actual UI payloads/DOM; desktop screenshot workflow uses synthetic fixtures |
| ESLint / typescript-eslint / Prettier | Frontend static checks and formatting | Keep accessible controls and TypeScript predictable |
| Node.js / npm | Node 24 reference; exact npm recorded at runtime | Locked frontend install through `npm ci` |
| Docker Compose | Container orchestration | Repeatable local topology and named volumes; not horizontal scalability |
| NGINX | Official `stable-alpine` deployment image | Static frontend and same-origin API proxy; record actual image digest |
| GitHub Actions / pre-commit | CI and local hygiene | Read-only checks; no automatic release or deployment |
| Mermaid | Source diagrams in Markdown | Reviewable architecture/lifecycle documentation; color is supplementary |

See manifests for every pin: [backend runtime](../backend/requirements.txt), [core](../backend/requirements-core.txt), [tests](../backend/requirements-test.txt), [developer requirements](../backend/requirements-dev.txt), [frontend](../frontend/package.json) and [lockfile](../frontend/package-lock.json).

## Why the architecture uses two evidence paths

Complete calculations read the canonical ledger; top-k retrieval is unsuitable as a complete operand set. Narrative evidence remains bounded and model-assisted. Models propose sentence selections, not authoritative arithmetic. The API validates identity, source wording and response shape. See [architecture](../ARCHITECTURE.md) and [decisions](index.md#design-decisions).

## When to reconsider a component

Change a parser, encoder, model or database only against a documented requirement and representative benchmark. Preserve source/cell behavior, compare latency/RAM and test migration/recovery. Distributed storage, queues, authentication and multi-user architecture belong to a separately scoped extension, not an implied capability of this MVP.
