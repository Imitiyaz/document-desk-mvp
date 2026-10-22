# Data locality and privacy in the Document Desk MVP

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## What stays local in the supplied setup

The native and Docker guides run the application on the local machine. Uploaded bytes are parsed locally; extracted records and embeddings are stored locally; supported calculations run in the API process. With Ollama on the same host, narrative questions send selected document context to that local service rather than a hosted AI provider.

The application does not require a hosted AI subscription for document inference. The AI tools used to develop the project are not runtime services of this application.

## Connections and configuration that change the boundary

**Table PRIV-01 — Local processing and possible external connections.**

| Area | Supplied behavior | What to check |
| --- | --- | --- |
| Browser/API | Loopback URLs; same-origin frontend proxy | Do not expose the unauthenticated API as a public service |
| Narrative model | Native localhost or Docker's host Ollama address | A remote `OLLAMA_BASE_URL` sends the prompt/context to that endpoint |
| Embeddings | Sentence Transformers runs BGE in the backend | First use may download model files from Hugging Face |
| Dependencies/images | npm, pip, container images and model downloads | These are external setup/update services, not evidence of an air-gapped installation |
| Telemetry | Compose disables named telemetry settings | No packet-level egress audit or universal third-party no-telemetry guarantee is claimed |
| Logs/screenshots/backups | Local outputs can contain questions and extracted source text | Apply retention and access rules; do not publish them automatically |

Model caches can reduce repeated downloads. That alone does not establish offline readiness: verify the complete environment and its outbound behavior if your use requires it.

## Retention and user actions

Temporary upload files are removed after extraction. Extracted facts, text and vectors remain in the workspace until document removal/reset or deliberate storage cleanup. Chat state is process-local and is not a permanent archive.

New chat does not delete indexed documents. Removing a document does not remove copies in backups, screenshots, logs or the original source system. See [cleanup](cleanup.md) and [backup/restore](operations.md).

## Suitability

Local inference is a useful privacy boundary, not a substitute for access control, endpoint security or a review of the supplied dependency/model terms. This MVP has no authentication, tenant isolation or secure-erasure guarantee. Read [Security](../SECURITY.md) before changing the deployment.
