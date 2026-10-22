# Native setup — run without Docker and verify the first answers

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

This is the complete **non-Docker** route. It starts the real API, embeddings and local Ollama model, plus the Vite development server. Choose this guide **or** [Docker deployment](docker.md) for your first run. Both use the same application; their document stores are separate. Controlled test servers are a third, explicitly separate mode described in [testing](testing.md).

## Prerequisites and the project folder

**Table SETUP-T01 — Native prerequisites and their purpose.**

| Install | Purpose and reference |
| --- | --- |
| Python 3.12, 64-bit | Reference interpreter for the supplied requirements and container; [Python downloads](https://www.python.org/downloads/) |
| Node.js 24 with npm | Locked frontend installation and development server; [Node downloads](https://nodejs.org/en/download) |
| Ollama | Separate local narrative-model server; [Ollama downloads](https://ollama.com/download) |
| Git, when cloning/contributing | Not required to run an extracted source ZIP; [Git downloads](https://git-scm.com/downloads) |
| Network access for installation | Python/npm packages and separately licensed model downloads; weights are not in this source ZIP |
| Available disk and memory | Dependencies, BGE cache, Ollama weights and document stores; no universal RAM/capacity guarantee is claimed |

Use a **new extraction folder**. Do not extract over another workspace, copy an old environment, or overwrite an existing index. The ZIP contains a top-level `rag-mvp` folder. The **project root** is the folder that directly contains `README.md`, `release.json`, `compose.yaml`, `backend` and `frontend`. Its parent is not the project root.

Reopen PowerShell after installing prerequisites. The commands below use each environment's Python directly; activation and execution-policy changes are unnecessary. Python 3.14 was used in earlier target-laptop checks with an existing environment; that is not a claim that every current ML dependency supports a fresh 3.14 installation. Use 3.12 for this documented clean install.

## Windows PowerShell installation

### 1. Select your actual project root and check prerequisites

Paste this block into PowerShell. When prompted, paste the **full path to your extracted `rag-mvp` folder**, without surrounding quotes. No example folder is silently selected.

```powershell
& {
    $selectedRoot = Read-Host 'Full path to the extracted rag-mvp folder (no surrounding quotes)'
    Set-Location -LiteralPath $selectedRoot -ErrorAction Stop
    foreach ($relative in @('release.json', 'compose.yaml', 'backend\requirements-dev.txt', 'frontend\package-lock.json')) {
        if (-not (Test-Path -LiteralPath $relative -PathType Leaf)) {
            throw "Wrong/incomplete project root: missing $relative. Stop before installing."
        }
    }
    Write-Host 'PROJECT ROOT:' (Get-Location).Path
    py -3.12 --version
    if ($LASTEXITCODE -ne 0) { throw 'Install 64-bit Python 3.12 and reopen PowerShell.' }
    node --version
    if ($LASTEXITCODE -ne 0) { throw 'Install Node.js 24 and reopen PowerShell.' }
    npm --version
    if ($LASTEXITCODE -ne 0) { throw 'npm is unavailable. Repair the Node.js installation.' }
    ollama --version
    if ($LASTEXITCODE -ne 0) { throw 'Install Ollama and reopen PowerShell.' }
}
```

Expect Python `3.12.x` and Node `v24.x`. Stay in this root for Steps 2–4. If a block stops, fix its first error before continuing.

### 2. Create the backend environment

```powershell
& {
    if (Test-Path -LiteralPath '.venv') { throw '.venv already exists. Reuse it only after checking its origin; do not overwrite it.' }
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
    & '.\.venv\Scripts\python.exe' -m pip install -r backend/requirements-dev.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Read the first package error; do not start the API.' }
    & '.\.venv\Scripts\python.exe' -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Installed dependency consistency check failed.' }
}
```

The native Python environment is intentionally located at the project root, `rag-mvp/.venv`, rather than inside `backend`. Run the API from that root using the commands below.

`requirements-dev.txt` includes runtime dependencies, quality tools and synthetic-fixture generators. A runtime-only alternative is `backend/requirements.txt`. For controlled tests use a **different** `.test-venv` with `backend/requirements-test.txt`; do not mix it into the runtime environment. Direct pins are supplied; Python transitive dependencies are not a complete hash-locked cross-platform distribution.

### 3. Create configuration without overwriting local settings

```powershell
& {
    if (-not (Test-Path -LiteralPath '.env' -PathType Leaf)) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env' -ErrorAction Stop
    }
    if (-not (Test-Path -LiteralPath '.env' -PathType Leaf)) { throw '.env was not created.' }
    Write-Host 'Configuration exists. Review .env before starting the API.'
}
```

The default native store is `./data/processed/chroma_db`. Keep that store together with its SQLite ledger. The API reads `.env` relative to its working directory, so launch from this root. Review [configuration](configuration.md) before changing models, indexes or endpoints. No credentials are required for the default local model services.

### 4. Start Ollama and check the installed model

Start the installed **Ollama application**. If your installation has no service running, run `ollama serve` in another terminal and leave it running. An occupied 11434 port may mean the intended service already exists; inspect it rather than starting a second server.

```powershell
ollama list
Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -ErrorAction Stop
```

If `llama3.1:8b-instruct-q4_K_M` is absent, run this once, then repeat `ollama list`:

```powershell
ollama pull llama3.1:8b-instruct-q4_K_M
if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Do not claim narrative-model readiness.' }
```

Downloads require acceptance of the model's separate terms. The configured model is approximately 4.9 GB of weights; inference also needs runtime/context memory. See [third-party notices](../THIRD_PARTY_NOTICES.md). The app does not install Ollama models automatically.

## Start the native application

### 5. Terminal 1 — real API and embedding model

Open a new PowerShell terminal and run the complete block. Use the same project root selected above.

```powershell
& {
    Set-Location -LiteralPath (Read-Host 'Full path to the same extracted rag-mvp folder (no surrounding quotes)') -ErrorAction Stop
    if (-not (Test-Path -LiteralPath '.\.venv\Scripts\python.exe' -PathType Leaf)) { throw 'This folder has no installed native environment. Complete Steps 1–3.' }
    $env:PYTHONUTF8 = '1'
    $env:ANONYMIZED_TELEMETRY = 'False'
    $env:OTEL_SDK_DISABLED = 'true'
    $env:DO_NOT_TRACK = '1'
    & '.\.venv\Scripts\python.exe' -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
}
```

The first start downloads `BAAI/bge-base-en-v1.5` if not cached. Wait for **Application startup complete** and the 127.0.0.1:8000 URL. Leave this terminal running. Use one worker; conversations and the operation lock are process-local. Do not use `--reload` for a persistent demonstration workspace. Telemetry opt-out flags are not an OS network-isolation guarantee.

### 6. Terminal 2 — install and start the frontend

```powershell
& {
    Set-Location -LiteralPath (Read-Host 'Full path to the same extracted rag-mvp folder (no surrounding quotes)') -ErrorAction Stop
    if (-not (Test-Path -LiteralPath '.\frontend\package-lock.json' -PathType Leaf)) { throw 'Select the project root, not its parent or frontend folder.' }
    Set-Location -LiteralPath '.\frontend' -ErrorAction Stop
    npm ci --include=dev --bin-links=true
    if ($LASTEXITCODE -ne 0) { throw 'Frontend installation failed; do not continue to npm run dev.' }
    if (-not (Test-Path -LiteralPath '.\node_modules\.bin\vite.cmd' -PathType Leaf)) { throw 'Local Vite executable is missing. Inspect the installation output.' }
    $env:VITE_API_BASE_URL = '/api'
    npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
}
```

Leave it running. Vite serves **http://127.0.0.1:5173/** and forwards `/api` requests to the API on port 8000. It is a development server, not a public hosting configuration. On later starts, reuse the installed dependencies and run only the environment setting and `npm run dev` from `frontend`; a reinstall is unnecessary when the lockfile has not changed.

### 7. Terminal 3 — verify API and browser-proxy readiness

```powershell
& {
    Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -ErrorAction Stop
    Invoke-RestMethod -Uri 'http://127.0.0.1:8000/ready' -ErrorAction Stop
    Invoke-RestMethod -Uri 'http://127.0.0.1:5173/api/ready' -ErrorAction Stop
}
```

Expect `ok`, `ready`, `ready`. These establish initialized resources and the proxy route, **not** model quality or answer correctness. Then perform Step 8; opening the homepage alone is not application verification.

### 8. Verify the application in the browser

For native setup open **http://127.0.0.1:5173/**. For Docker open **http://127.0.0.1:8080/**, or the port you selected. All file paths below are **relative to your extracted project root**. Use only supplied synthetic fixtures in this smoke test.

1. Wait until the document library finishes loading. In a new workspace it shows **0 indexed documents**. Click **Add a document** and browse into `backend\tests\fixtures\sample_sales.xlsx`. Wait for its indexed message; do not upload again while it processes.
2. Confirm `sample_sales.xlsx` is selected. Leave **Optional refinements** closed. Ask **What was the Q3 revenue for North in the Q3 Sales sheet?** using **Find answer**. Expect **45,000** before the evidence. Open **View evidence** and check **Q3 Sales / row 2**, North **A2**, Revenue **B2**. A matching number with the wrong row/cell is a failure.
3. In the same chat ask **And South?** Expect **38,000**, Q3 Sales row **3**, **B3**. Tab to a citation and press Enter: evidence should open and focus its matching source reference.
4. Click **New chat**. The indexed document must remain. Ask **What is the combined Q3 revenue for North, South, and East in the Q3 Sales sheet?** Expect **124,000 = 45,000 + 38,000 + 41,000**, with all three operand records and their cell references.
5. Upload `backend\tests\fixtures\acceptance\hours.xlsx`. Ask **What is the sum of Hours?** Expect an **available-value subtotal of 15.75 hours**, from **7.5 + 8.25 + 0**. Ben's missing **B4** must be disclosed and excluded, not replaced with zero. Ask **What Hours are recorded for Ben?** Expect missing source information. Ask **Total hours for Zenzee?** Expect no matching records, not Asha's hours.
6. Upload `backend\tests\fixtures\acceptance\operations.pdf`. Ask **Is Orchid production launch approved and when is the next review?** Expect **not approved**, **2026-11-03**, and **page_4 / full_page_text**. In Request details, actual model success uses `source_grounded_summary` with the configured model. A clearly labeled excerpt fallback is useful degraded behavior, but **does not pass** this actual-model synthesis check. Narrative generation can take tens of seconds; do not click repeatedly.
7. In that same chat ask **Is Rose production launch approved and when is the next review?** Expect **no matching source evidence for Rose**, no borrowed Orchid facts/date and no substituted citation.
8. Test **Remove** on a synthetic document: choose **Keep data** in the first confirmation, verify the document/answer remain, then remove it and verify only that document disappears. **Reset workspace** is a separate confirmed deletion of all indexed review documents; use it only when you intend that deletion. **New chat** does not delete indexed documents.
9. Check **License & source**. Before serving other users, provide the corresponding source for the exact deployment as described in [source availability](../LICENSE-NOTICE.md), and configure its working source link.

**Table SETUP-T02 — Smoke-test pass criteria.**

| Check | Required result |
| --- | --- |
| Lookup and follow-up | 45,000 / B2, then 38,000 / B3, correct document and sheet |
| Calculation | 124,000 and all three original operands; no hidden top-k-only total |
| Missing versus absent | Ben's blank is missing; Zenzee has no matching record; zero remains an operand |
| Narrative | Orchid negation/date/page retained; Rose does not receive those facts |
| UI lifecycle | New chat retains documents; canceled removal retains data; confirmed removal is selective |

If a result differs, preserve the exact question, selected file/scope, displayed answer, status/path, warnings and citations. A screenshot is useful; do not share confidential originals. See [troubleshooting](troubleshooting.md). Controlled testing and screenshot automation are optional next steps in [testing](testing.md) and [screenshots](screenshots.md), not prerequisites for this manual smoke test.

## Stop, restart and preserve data

Press **Ctrl+C** in Terminal 2, then Terminal 1, and wait for API shutdown. Restart with Steps 5–7; indexed documents persist, process-local conversations do not. Same-name re-upload returns duplicate `409`; select the existing document instead of overwriting it. Use [cleanup](cleanup.md) for targeted deletion and [operations](operations.md) for offline backup/restore.

## Linux/macOS native commands

The reference interpreter remains Python 3.12. These commands require installed Python, Node.js 24 and a running Ollama service. They are a platform recipe, not a claim of a fresh macOS acceptance run. Open a terminal **in the actual extracted project root**; verify it with `test -f release.json` and `test -f backend/requirements-dev.txt` before continuing.

Installation:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
.venv/bin/python -m pip check
test -f .env || cp .env.example .env
ollama list
# Only if the configured model is absent:
ollama pull llama3.1:8b-instruct-q4_K_M
```

Stop on any failed command. In Terminal 1, from the root:

```bash
export PYTHONUTF8=1
export ANONYMIZED_TELEMETRY=False
export OTEL_SDK_DISABLED=true
export DO_NOT_TRACK=1
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1
```

In Terminal 2, open the same root, then:

```bash
cd frontend
npm ci --include=dev --bin-links=true
export VITE_API_BASE_URL=/api
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

In the browser perform the same Step 8 checks. Stop both servers with Ctrl+C. Do not bypass failed installation, model or readiness checks.
