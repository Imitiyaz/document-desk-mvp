# Desktop screenshots — controlled regression and actual-model demonstrations

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## Privacy and evidence boundary

Capture the real application with the **supplied synthetic fixtures only**. Raw PNGs, traces, responses and manifests stay under ignored local output folders. Only deliberately reviewed images in the [public UI gallery](ui.md) are included in the source ZIP. Review any further image before promotion or article use. No capture command publishes to GitHub, Medium, LinkedIn or another service.

**Table CAP-01 — Two capture modes with different meanings.**

| Mode | App/backend | What a pass means | Output |
| --- | --- | --- | --- |
| Controlled desktop test | Real browser/UI/API/parsers/SQLite, explicit tiny encoder/scripted model/fake vectors | Tested interaction, source/value correctness and layout against supplied expectations | `frontend/test-results/desktop` |
| Actual-model capture | Ordinary native or Docker API, real BGE/store and configured host Ollama | Focused lookup, subtotal, actual-model sentence selection and unknown-subject behavior observed | Root `reports/screenshots-live/<fresh timestamp>` |

Do not label controlled screenshots as measured model performance. A screenshot is a point-in-time observation, not universal accessibility certification. A model tag printed by the server is not an independent attestation of how its host is configured.

## Controlled desktop capture

Prepare the lightweight `.test-venv`, frontend dependencies and Chromium as described in [testing](testing.md). Stop any native API/Vite servers using 8000/5173; Playwright owns its isolated servers and refuses to reuse an ordinary workspace.

```powershell
& {
    Set-Location -LiteralPath (Read-Host 'Full path to the extracted rag-mvp folder (no surrounding quotes)') -ErrorAction Stop
    $testPython = Join-Path (Get-Location).Path '.test-venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $testPython -PathType Leaf)) { throw 'Complete the lightweight testing prerequisites first.' }
    $env:PYTHON_EXECUTABLE = $testPython
    $env:RAG_TEST_VECTOR_BACKEND = 'fake'
    $env:PYTHONUTF8 = '1'
    Set-Location -LiteralPath '.\frontend' -ErrorAction Stop
    npm run test:desktop
    if ($LASTEXITCODE -ne 0) { throw 'Desktop verification failed. Preserve its current test-results.' }
}
```

The suite covers 1280, 1440 and 1920-pixel desktop widths, actual request/response values and cells, follow-ups, missing-value warnings, unknown subjects, citation keyboard focus, layout overflow and safe cancellation of the **Reset workspace** confirmation. Scrollable evidence tables are allowed; page-wide horizontal overflow is not.

## Actual-model desktop capture

Start an **empty isolated** native workspace using [setup](setup.md), or an unused Docker review project using [Docker](docker.md). Confirm the library has zero documents. The capture helper does not reset, delete or overwrite an existing catalog. If you already ran the manual smoke test, either deliberately remove only those synthetic documents through the UI, or start a separate empty review workspace; do not clear ordinary user data to run capture.

Docker runs the application without host npm, but this optional screenshot tool needs host Node/npm and Playwright. From your actual extracted root:

```powershell
& {
    Set-Location -LiteralPath (Read-Host 'Full path to the extracted rag-mvp folder (no surrounding quotes)') -ErrorAction Stop
    Set-Location -LiteralPath '.\frontend' -ErrorAction Stop
    npm ci --include=dev --bin-links=true
    if ($LASTEXITCODE -ne 0) { throw 'Capture dependency installation failed.' }
    npx playwright install chromium
    if ($LASTEXITCODE -ne 0) { throw 'Chromium installation failed; capture has not run.' }
}
```

Stay in that `frontend` terminal. For Docker on port 8080 run:

```powershell
npm run capture:live -- --url http://127.0.0.1:8080/ --width 1440
if ($LASTEXITCODE -ne 0) { throw 'Capture failed. Preserve the CAPTURE REPORT manifest and any images; do not blindly rerun.' }
```

For native use `--url http://127.0.0.1:5173/`; for another Docker port use the actual loopback port. Only `http://127.0.0.1:<port>/` origins without credentials/query parameters are accepted. Widths 1280, 1440 and 1920 are supported. An explicit `--output` must name a **new** directory; an existing output is never overwritten. `BROWSER_EXECUTABLE` can select a compatible installed browser deliberately; record its actual version and do not treat a failed launch as passed.

### Scenarios and expected image content

**Table CAP-02 — Four actual-model capture scenarios.**

| Scenario | Synthetic upload | Required facts |
| --- | --- | --- |
| `lookup` | `demo-sales.xlsx` from the supplied sample workbook | North 45,000, Q3 Sales row 2, B2 |
| `subtotal` | `demo-hours.xlsx` from the acceptance fixture | 15.75; partial subtotal; missing source value remains disclosed |
| `actual-model-narrative` | `demo-operations.pdf` from the acceptance fixture | Orchid **not approved**, next review **2026-11-03**, actual model and `source_grounded_summary` |
| `unknown-subject` | Same synthetic PDF | Rose no evidence; no Orchid/date/citation substitution |

Each question is sent through the browser's real controls. The helper saves a request entry first, then HTTP status/raw text and parsed response **before** checking the answer. Failed HTTP/JSON, rejected fallback, request timeouts and screenshot failures remain recorded as failures. If possible a failed response also gets a `-failed.png` screenshot; secondary screenshot errors do not replace the original failure. Earlier completed captures remain in the same manifest.

Successful captures record the displayed answer plus PNG. A fallback with correct source facts is **not** counted as successful actual-model synthesis. A passed four-scenario run requires all four checks. A separately successful request does not change the status of a failed capture run.

The command prints **CAPTURE REPORT: <full path to manifest.json>**. Save that exact manifest and its images for review. `application_version`, capture-schema version, model/path metadata and per-scenario validation/status distinguish what happened. Source documents remain indexed afterward for visual inspection; this is deliberate. Do not rerun against that now-populated catalog without explicitly preparing an empty isolated workspace.

## Review before using article assets

Check that the selected document, effective question, answer, warnings and citation are visible together. Review negation/date, missing versus absent values, subtotal wording, original cell references and keyboard focus. Inspect browser chrome, paths, names and any developer console for unintended private information.

Keep the corresponding source revision and model/runtime mode with each chosen image. If a result was degraded, describe it honestly or capture a separately verified successful request; never edit an image to invent an answer. Raw manifests/logs can contain more content than the image and need their own privacy review. Use [cleanup](cleanup.md) to retire unneeded local artifacts after retention/recovery needs are satisfied.


## Promote reviewed images into the public gallery

Capture is opt-in and separate from normal setup/testing. Tests and capture commands do not stage files or publish screenshots.

1. Inspect each selected PNG and its saved response. Use synthetic documents only. Check the question, result, warnings, citations and runtime mode.
2. Keep the original run folder under ignored reports. Select only individually passed captures; a failed narrative/fallback capture cannot be promoted as a successful model answer.
3. From the extracted project root, run this block. Paste the exact folder containing the capture's `manifest.json`, without surrounding quotes:

```powershell
& {
    Set-Location -LiteralPath (Read-Host 'Full path to the extracted rag-mvp folder (no surrounding quotes)') -ErrorAction Stop
    $captureRun = Read-Host 'Full path to the reviewed capture run folder (no surrounding quotes)'
    python .\tools\ui_gallery.py --from-run $captureRun --scenarios lookup subtotal --reviewed
    if ($LASTEXITCODE -ne 0) { throw 'Gallery promotion stopped. Keep the original run and the existing gallery.' }
    python .\tools\catalog.py
    if ($LASTEXITCODE -ne 0) { throw 'Catalog generation stopped.' }
    python .\tools\ui_gallery.py --check
    if ($LASTEXITCODE -ne 0) { throw 'Gallery checks failed. Review the reported backup and output.' }
    python .\tools\check_repository.py
    if ($LASTEXITCODE -ne 0) { throw 'Repository checks failed.' }
}
```

The shipped gallery contains lookup and subtotal images. Promotion replaces only the selected image files, updates their mode/hash/dimension metadata and regenerates `docs/ui.md`. Overwritten gallery files are backed up under `reports/ui-gallery-backups/<timestamp>/`; caught write/check errors restore the originals. Application data and Git state are untouched.

To include independently passed narrative/no-evidence captures as well, add `actual-model-narrative unknown-subject` after `--scenarios`. Review all selected images first. The source catalog must be regenerated when new asset files are added.

Markdown image links render the committed files at their relative paths. GitHub does not discover local ignored test results automatically. Review and commit only the selected gallery changes in your normal contribution workflow; never force-add an entire reports/test-results directory.
