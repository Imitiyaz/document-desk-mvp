# Configuration reference

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

The backend uses `pydantic-settings` in `backend/app/core/config.py`. Environment variables override values from root `.env`; unknown keys are ignored. Relative paths resolve from the process working directory. Invalid typed values fail during configuration loading.


**Table CONFIGURATIO-T01 — Configuration reference.**

| Variable | Default | Meaning / boundary |
| --- | --- | --- |
| APP_ENV | development | Informational setting; does not enable authentication or hardening |
| LOG_LEVEL | INFO | Central loguru threshold |
| OLLAMA_BASE_URL | http://localhost:11434 | Model server; document context is sent here |
| OLLAMA_MODEL | llama3.1:8b-instruct-q4_K_M | Installed Ollama tag |
| OLLAMA_CONTEXT_LENGTH | 8192 | Accepted range 4096–32768 |
| OLLAMA_NUM_PREDICT | 512 | Accepted range 64–2048 |
| EMBEDDING_MODEL | BAAI/bge-base-en-v1.5 | SentenceTransformer identifier; initial download may be needed |
| CHROMA_PERSIST_DIR | ./data/processed/chroma_db | Managed vector/index directory and ledger location |
| CHROMA_COLLECTION_NAME | documents | Collection identity |
| SQLITE_DB_PATH | ./data/processed/metadata.sqlite3 | Legacy accepted key; does not select the current source ledger |
| RETRIEVAL_TOP_K | 5 | Default ranked retrieval count, 1–100 |
| API_HOST | 0.0.0.0 in code | Available config only; documented Uvicorn command explicitly binds 127.0.0.1 |
| API_PORT | 8000 | Available config only; Uvicorn command controls the actual port |
| CORS_ALLOWED_ORIGINS | localhost:5173 and 127.0.0.1:5173 HTTP origins | Browser origin allowlist; not authentication |
| MAX_UPLOAD_BYTES | 20971520 | 20 MiB file limit; middleware allows a further 1 MiB multipart overhead |
| UPLOAD_TEMP_DIR | ./data/processed/uploads | Temporary upload staging |
| MAX_XLSX_EXPANDED_BYTES | 104857600 | 100 MiB expanded ZIP budget |
| MAX_EXTRACTED_ROWS | 25000 | Extraction budget; not a tested throughput promise |
| MAX_PDF_PAGES | 200 | Page extraction ceiling |
| MAX_XLSX_COLUMNS | 512 | Spreadsheet width ceiling; accepted setting range 1–16384 |

The current ledger is `CHROMA_PERSIST_DIR/<collection>-records.sqlite3`. Treat it and the Chroma files as one workspace backup unit.

## Frontend

`VITE_API_BASE_URL=/api` works with the supplied Vite development proxy. Vite environment values are build-time/client-visible configuration; never put credentials in a `VITE_*` variable. A static production server must provide its own `/api` routing or use an explicitly configured API URL and matching CORS policy.

## Isolation and model changes

Use a new `CHROMA_PERSIST_DIR` for experiments and tests. Model name and embedding dimension are bound to the ledger. Do not point a changed embedding model at an existing incompatible index; select a new workspace and ingest originals again.

Ollama runs separately. Its model cache is not removed by workspace reset. Hugging Face caches are also outside the application workspace.

## Network and privacy

The default model endpoint is local. Setting it to a remote address transfers selected document context to that address; assess access, TLS and data permissions first. Initial package/model downloads and library telemetry are separate network concerns.

`ANONYMIZED_TELEMETRY=False`, `OTEL_SDK_DISABLED=true` and `DO_NOT_TRACK=1` must be actual process environment variables for supporting libraries to see them. Adding arbitrary keys to application `.env` does not automatically export them to other libraries.
