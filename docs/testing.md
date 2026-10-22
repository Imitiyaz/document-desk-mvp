# Testing and evaluation

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## Test layers and what they establish


**Table TESTING-T01 — Test layers and what they establish.**

| Layer | Components exercised | Substitutions / limits |
| --- | --- | --- |
| Python default suite | Parsers, cleaning, structured operations, lifecycle, API schemas/errors and oracles | Test encoders/vector collections/LLMs where injected |
| React component suite | Forms, answer rendering, evidence and interactions | Mocked HTTP client |
| Browser suite | Real browser, frontend, HTTP routes, parsers and SQLite | TinyEncoder and ScriptedLLM; vector backend explicitly selected |
| Native vector tests | Chroma adapter and persistence | Supplied/test vectors unless combined with model tests |
| Embedding tests | Real BGE loading/encoding/ranking | Network download may be required |
| Ollama tests | Real model transport and bounded prompt evaluations | Some contexts hand-built; some cases explicitly xfail/skip |

No single row proves general answer accuracy. Browser “mobile” is a Chromium viewport emulation, not physical iOS/Safari certification.

## Isolated backend checks

Create a lightweight environment separate from the normal runtime. From the repository root on Windows:

```powershell
py -3.12 -m venv .test-venv
.\.test-venv\Scripts\python.exe -m pip install -r backend/requirements-test.txt
$env:PYTHONUTF8 = '1'
Set-Location backend
..\.test-venv\Scripts\python.exe tools/offline_pytest.py -q --cov=app --cov-report=term-missing
..\.test-venv\Scripts\python.exe -m ruff check app tests tools
..\.test-venv\Scripts\python.exe -m black --check app tests tools
..\.test-venv\Scripts\python.exe -m mypy app --ignore-missing-imports
```

On Linux/macOS use `python3.12 -m venv .test-venv` and `../.test-venv/bin/python` for the backend-directory commands.

The default pytest marker expression excludes embedding_model, vectorstore and ollama cases. The offline runner denies external Python socket/DNS activity and opts out of supporting telemetry. It refuses environments containing selected native ML/vector runtimes; it is not an OS network sandbox. Installation itself uses the network.

Use the normal runtime environment for explicitly selected real-resource tests:

```powershell
Set-Location -LiteralPath (Read-Host 'Full path to the extracted rag-mvp folder (no surrounding quotes)') -ErrorAction Stop
Set-Location -LiteralPath '.\backend' -ErrorAction Stop
..\.venv\Scripts\python.exe -m pytest -q -m vectorstore
..\.venv\Scripts\python.exe -m pytest -q -m embedding_model
..\.venv\Scripts\python.exe -m pytest -q -m ollama
```

Inspect skips, xfails and test descriptions. Some legacy prompt tests evaluate raw generation with hand-built evidence; they do not establish the UI narrative path's full correctness.

## Frontend checks

From `frontend`:

```powershell
npm ci --include=dev --bin-links=true
npm run typecheck
npm run typecheck:browser-contract
npm run lint
npm run test:coverage
npm run test:ui-checker
npm run build
```

## Actual browser requests and desktop/mobile comparison

Close any API/frontend server already using ports 8000/5173. Playwright owns both test servers and refuses to reuse an ordinary workspace server.

```powershell
Set-Location -LiteralPath (Read-Host 'Full path to the extracted rag-mvp folder (no surrounding quotes)') -ErrorAction Stop
Set-Location -LiteralPath '.\frontend' -ErrorAction Stop
$env:PYTHON_EXECUTABLE = (Resolve-Path '..\.test-venv\Scripts\python.exe').Path
$env:RAG_TEST_VECTOR_BACKEND = 'fake'
$env:PYTHONUTF8 = '1'
npx playwright install chromium
npm run test:e2e
if ($LASTEXITCODE -ne 0) { throw 'Browser tests failed; inspect test-results before comparing.' }
npm run test:ui-compare
if ($LASTEXITCODE -ne 0) { throw 'Browser contract comparison failed. Preserve its reports.' }
npm run test:desktop
if ($LASTEXITCODE -ne 0) { throw 'Desktop-width verification failed. Preserve its reports.' }
```

On Linux/macOS set `PYTHON_EXECUTABLE` to an absolute `.test-venv/bin/python` path and export the same test-backend variables. Some Linux hosts need `npx playwright install --with-deps chromium`; review its system-package changes first.

The shared workflow config uses an isolated temporary index, one worker, no retries and separate desktop/mobile projects. Desktop-only width scenarios are excluded from that comparison run and selected explicitly by `test:desktop`, which covers 1280, 1440 and 1920 pixels. CI runs both suites. Shared browser artifacts use `test-results/e2e`; desktop captures use `test-results/desktop`, so running the desktop suite retains the shared comparison reports. The fake vector backend is an explicit controlled mode. To exercise native Chroma instead, use the fully installed runtime Python, set `RAG_TEST_VECTOR_BACKEND=real` and rerun deliberately.

Artifacts are written under `frontend/test-results/`. Comparators check each viewport against reviewed fixture expectations before checking equality; two identical wrong answers must fail. They verify source populations, operands, statuses, displayed values, warnings and citations. They are not pixel-diff accessibility certification.

## Independent references and mutation checks

Oracles under `backend/tools` use independently stated fixture facts, Decimal calculations or raw XLSX XML. Tests deliberately corrupt totals, omit operands, change scopes/citations and remove warnings. Preserve these checks when extending answer shapes.

Do not generate expected values from the application under test. Test ordinary frontend payloads, reordered conversations, fresh sessions and changed populations. Explicit API filters must not substitute for natural-language acceptance cases.

## Quality checks against a running API

`python -m tools.quality_recheck --base-url http://127.0.0.1:8000` runs from `backend` against a deliberately fresh isolated index. It uploads fixture filenames and stops on duplicate 409; it does not replace existing data. Output defaults to ignored `reports/quality/` at repository root.

A successful synthetic run is bounded evidence. Representative business documents, unknown entities, ambiguous labels, contradictory/temporal facts, malicious document instructions, realistic failures and performance still require separate evaluation.

## Repository checks

Run `python tools/check_repository.py`, `python tools/catalog.py --check`, and `python -m unittest discover -s tools/tests -v` from the repository root. They check public-distribution boundaries, local links, complete inventory, captioned/registered diagram copies, labeled flow edges and table titles. Catalog tests cover real Windows/POSIX sorting semantics and canonical LF/CRLF handling. These are heuristic guards, not a complete secret, license or security audit.

`npm run test:ui-checker` also exercises live-capture failure recording: rejected source-excerpt fallback, HTTP errors, invalid JSON, transport failures and screenshot failures must preserve their evidence without becoming passes. See [screenshots](screenshots.md).

## Current desktop release batch

Use a separate lightweight `.test-venv` containing `backend/requirements-test.txt`, and install frontend dependencies with `npm ci --include=dev --bin-links=true`. Install Chromium once with `npx playwright install chromium`. From the repository root:

```powershell
Set-Location -LiteralPath (Read-Host 'Full path to the extracted rag-mvp folder (no surrounding quotes)') -ErrorAction Stop
.\.test-venv\Scripts\python.exe tools/verify_release.py
```

The batch installs nothing, checks repository/catalog and source-helper tests before backend/frontend layers, stops on the first failure and prints a single `REPORT ZIP` even on failure. It retains previous browser results under an ignored `test-results-prior-*` folder rather than mixing them into the new evidence. Model/vector substitutes are explicit. Docker/native-model capacity is separate.

The desktop project checks 1280/1440/1920 widths for actual values/cells, follow-ups, subtotal operands, unknown subject handling, keyboard evidence and full-width overflow. Mobile projects remain available for experimentation through the Playwright config; they are outside the supported desktop MVP scope. See [screenshots](screenshots.md).

Negative narrative tests use varied names, lowercase forms, exact word boundaries, mixed-project source text, incorrect model selections and empty selections. Maintenance tests reject path traversal, symlinks, duplicate/unsafe members and restoring onto existing data. These extend, rather than replace, numeric/source corruption tests.

## Read negative-test output correctly

Repository helper tests deliberately exercise rejected catalog drift, unsafe project names and unavailable endpoints. Those cases can print a failure/error message while the enclosing test succeeds. Use the final unittest summary and process exit status to decide whether the suite passed. Run `python tools/catalog.py --check` separately to check the actual checkout's catalog; that command must exit successfully.
