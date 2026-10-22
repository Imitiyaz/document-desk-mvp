# Cleanup — remove generated artifacts without losing source or document data

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## Choose the retention domain first

Cleanup is **selective**, not a request to erase the checkout. Keep the source, local configuration, original business documents and verified backups. Stop this checkout's test/watch/capture processes before cleaning their outputs; stop the API before touching its persistence directory. Do not kill unrelated processes to release a file lock.

**Table CLEAN-T01 — Generated data, ownership and safe default.**

| Component | Location / owner | Safe default and consequence |
| --- | --- | --- |
| Current chat | Process-local API state and browser conversation | **New chat** clears the active chat context; indexed documents stay |
| One indexed document | SQLite ledger plus Chroma | Use **Remove** with confirmation; removes that version's searchable evidence and associated chat state |
| All indexed documents | Current application workspace | **Reset workspace** is an explicit destructive action; do not use it to clean logs |
| Native persistent store | Configured `CHROMA_PERSIST_DIR`, default `data/processed/chroma_db` | Keep; offline backup/restore must include ledger and vectors together |
| Temporary upload staging | `UPLOAD_TEMP_DIR`, default `data/processed/uploads` | Requests normally remove temporary files; inspect orphans only after stopping the API |
| Test/report outputs | Root `reports`, frontend `test-results`, `playwright-report`, coverage outputs | Review/retain needed evidence first; delete only selected recreatable output directories |
| Test caches | `.pytest_cache`, `.ruff_cache`, `.mypy_cache`, Python `__pycache__` | Recreated by tools; cache removal is optional, not a correctness fix |
| Frontend build | `frontend/dist`, `*.tsbuildinfo` | Rebuild with `npm run build`; source and lockfiles must remain |
| Installed dependencies | `.venv`, `.test-venv`, `frontend/node_modules` | Normally keep; recreate from requirements/lockfile if deliberately reinstalling |
| Native BGE cache | Hugging Face cache or configured `HF_HOME` | May be shared by projects; keep unless deliberately reclaiming verified model files |
| Docker document store | `<project>_workspace` named volume | Keep unless an offline backup/restore is verified and deletion is intended |
| Docker BGE cache | `<project>_model_cache` named volume | Independent of host caches; deletion requires model re-download |
| Host Ollama models | Ollama's model store | Separate from project data and Docker volumes; may serve other projects |
| Backup archives | Selected native backup folder or `reports/backups` / Docker run `backup` directory | Keep independently of disposable reports; verify restoration before deletion |

Document removal/reset does not delete copies already present in backups, logs, screenshots or original source systems. It is not a guaranteed secure erase of storage media. Manage those retention domains according to your own policy.

## 1. Clear chat or indexed documents through the application

For a new question/session click **New chat**. For one document click its **Remove** action; the confirmation names the document. **Keep data** cancels. Use **Reset workspace** only when you intend to remove every indexed document in the selected workspace; confirm its displayed document count.

Do not manually remove individual Chroma/SQLite files while the API is running, and do not replace a missing source amount with zero to make cleanup/testing pass. For an index compatibility change, back up first, choose a new store or remove/re-upload the source through supported lifecycle actions.

## 2. Preview and optionally remove recreatable build/test outputs

This PowerShell block prompts for your root and first runs **`-WhatIf` only**. It does not delete anything. It deliberately **does not include the whole `reports` folder**, which can contain backups. Stop this checkout's test/watch servers before later deleting any listed folder.

```powershell
Set-Location -LiteralPath (Read-Host 'Full path to the extracted rag-mvp folder (no surrounding quotes)') -ErrorAction Stop
if (-not (Test-Path -LiteralPath '.\release.json' -PathType Leaf)) { throw 'Select the project root first.' }
$cleanupRoot = (Get-Location).Path
$recreatable = @(
    'frontend\dist',
    'frontend\coverage',
    'frontend\test-results',
    'frontend\playwright-report',
    'backend\htmlcov',
    'backend\.pytest_cache',
    'backend\.ruff_cache',
    'backend\.mypy_cache',
    '.pytest_cache',
    '.ruff_cache',
    '.mypy_cache'
)
foreach ($relative in $recreatable) {
    $candidate = Join-Path $cleanupRoot $relative
    if (Test-Path -LiteralPath $candidate) {
        Get-Item -LiteralPath $candidate | Select-Object FullName, Attributes
        Remove-Item -LiteralPath $candidate -Recurse -Force -WhatIf
    }
}
```

Review the printed absolute paths. If any selected path is a junction/symlink or redirects outside this checkout, do not proceed with recursive removal; inspect it separately. Do not change the list to include `data`, `.env`, source directories or model caches.

If you want to remove **one reviewed directory**, run this separate guarded block. Select a normal local directory, not a junction/reparse point. It accepts only the fixed relative names above, displays the absolute path again, and requires typing `DELETE`.

```powershell
& {
    if (-not $cleanupRoot -or -not $recreatable) { throw 'Run the preview block in this same terminal first.' }
    $relative = Read-Host 'One exact relative directory from the preview list'
    if ($relative -notin $recreatable) { throw 'That directory is not in the recreatable allowlist.' }
    $candidate = Join-Path $cleanupRoot $relative
    if (-not (Test-Path -LiteralPath $candidate -PathType Container)) { throw 'No such generated directory.' }
    $cursor = Get-Item -LiteralPath $candidate -Force -ErrorAction Stop
    while ($cursor -and $cursor.FullName -ne $cleanupRoot) {
        if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse point detected. Inspect manually; no removal performed.' }
        $cursor = $cursor.Parent
    }
    $nestedLinks = Get-ChildItem -LiteralPath $candidate -Recurse -Force -ErrorAction Stop |
        Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 }
    if ($nestedLinks) { throw 'Nested reparse point detected. Inspect manually; no removal performed.' }
    Write-Host 'REMOVE ONLY:' $candidate
    if ((Read-Host 'Type DELETE to remove this generated directory') -cne 'DELETE') { throw 'Canceled; no removal performed.' }
    Remove-Item -LiteralPath $candidate -Recurse -Force -ErrorAction Stop
}
```

Keep this terminal's inspected root/list unchanged. A concurrent filesystem change can invalidate any preview; use these commands only on your own stopped local checkout. On Linux/macOS inspect the same exact directories with `ls` and remove an individually reviewed generated path; do not translate this into an unreviewed `find ... -delete` across your home directory.

## 3. Retain or remove individual reports and screenshots

Verification tools create timestamped directories under `reports`; screenshot/capture manifests may include questions, answers and source extracts. Keep evidence needed to explain a release or a failure. Never assume a failed batch is disposable before its diagnosis is complete.

List report directories without deleting them:

```powershell
Get-ChildItem -LiteralPath (Join-Path $cleanupRoot 'reports') -Directory -ErrorAction Stop |
    Select-Object Name, LastWriteTime, FullName
```

Inspect the chosen run's contents. Preserve its backup archives and any required manifest/screenshots first. Use `Remove-Item -LiteralPath '<one reviewed full run-directory path>' -Recurse -WhatIf` for a preview; only remove `-WhatIf` after independently checking that exact path. Do not execute the angle-bracket placeholder literally. An associated report ZIP is a separate file; deleting it does not delete the original run directory or its backup.

Root `reports/backups`, a Docker run's `backup/workspace.tar.gz`, and an independently stored backup must **not** be treated as general cache. Keep at least a verified recovery copy before deleting application data. Generated artifacts remain ignored by Git; ignoring them does not dispose of them or make them safe to publish.

## 4. Native logs, orphan uploads and caches

By default application logs go to the console. If you deliberately redirected them to a file, rotate/delete that specific file only after its writer stops. Avoid dumping `.env` or raw business responses into public diagnostic logs.

Normal request cleanup removes staged uploads. For suspected orphans, stop the API, read your actual `UPLOAD_TEMP_DIR`, list it, confirm that no uploads are active, and remove only identified orphan temporary files. Do not confuse that directory with `CHROMA_PERSIST_DIR` or a user's original document folder.

Python caches, frontend `*.tsbuildinfo`, and `.coverage`/`coverage.xml`/`junit.xml` outputs can be removed individually after tools stop. They are not source. `node_modules` and virtual environments are dependency installations, not document stores: reinstalling them should be a deliberate troubleshooting choice. Keep `package-lock.json` and the requirements files; never delete the lockfile or install global Vite to repair a local missing executable.

Native Hugging Face, npm, pip, Playwright and Ollama caches can be shared by other applications. This guide does not bulk-delete global caches. Inspect their official tooling/settings and ownership before reclaiming a specific model/browser/package. Deleting weights means re-downloading them and does not fix an incorrect answer. Do not delete a model that another running application uses.

## 5. Docker logs, stopped services and volumes

Use the exact root/project/Compose settings from [Docker Step 1](docker.md#1-select-the-actual-source-folder-and-check-prerequisites). These commands require those variables in the same terminal.

```powershell
docker compose --project-directory $deskRoot -f $deskCompose -p $deskProject ps -a
docker compose --project-directory $deskRoot -f $deskCompose -p $deskProject logs --tail 100 backend frontend
docker volume ls --filter "label=com.docker.compose.project=$deskProject"
```

`logs --tail` only bounds the displayed output; it does not erase Docker's stored logs. Stopping with `stop` preserves containers/logs/volumes. `down` removes that project's service containers and network while retaining its named data/cache volumes. Removing/recreating service containers also removes their old container-log storage, so retain sanitized diagnostics first. Do not truncate Docker-managed log files by editing the Docker Desktop filesystem.

To stop/remove only this stack while keeping document data:

```powershell
docker compose --project-directory $deskRoot -f $deskCompose -p $deskProject down
if ($LASTEXITCODE -ne 0) { throw 'Shutdown failed; inspect the output before continuing.' }
```

### Deliberately destroy one reviewed project and both of its volumes

This is optional, destructive, and **not** a normal shutdown. Before running it, stop all writers, make an offline full backup, restore that backup in isolation and inspect the recovered source records. The selected project name must match the intended review deployment; a restored project's name is different.

```powershell
& {
    if (-not $deskRoot -or -not $deskCompose -or -not $deskProject) { throw 'Select the Docker root/file/project using its Step 1 first.' }
    if ($deskProject -notmatch '^rag-mvp-review') { throw 'This example is limited to a reviewed project name.' }
    docker volume ls --filter "label=com.docker.compose.project=$deskProject"
    Write-Host 'This destroys the selected project workspace AND embedding-cache volumes:' $deskProject
    if ((Read-Host 'After verifying an independent restore, type the exact project name to delete') -cne $deskProject) { throw 'Canceled; no deletion performed.' }
    docker compose --project-directory $deskRoot -f $deskCompose -p $deskProject down --volumes
    if ($LASTEXITCODE -ne 0) { throw 'Removal did not complete; inspect remaining project resources.' }
}
```

This does not delete backup files, host Ollama models, native indexes or images. Restore-test volumes retained by `verify_docker.py` belong to the separately reported restore project. Review and remove those independently if no longer needed.

Build cache and image layers may be shared. **Do not use global `docker system prune`, `docker volume prune`, Docker Desktop factory reset or a global cache wipe as project cleanup.** Reclaiming shared storage requires a separate review of other workloads. See [Docker volumes](https://docs.docker.com/engine/storage/volumes/) and [`compose down`](https://docs.docker.com/reference/cli/docker/compose/down/).

## 6. Verify after cleanup

Restart only what you intend to retain. Check catalog, an exact value/cell, missing-value behavior and model source when applicable. A deliberately reset/deleted workspace should be empty; a report/cache-only cleanup should leave indexed documents intact. Rebuild frontend artifacts or rerun the affected check only if needed; cache cleanup does not justify repeating every unrelated suite.


## 7. Optional native dependency reinstall

Stop this checkout's API, frontend, tests and capture processes first. Close any terminal using its activated environment. Open a fresh PowerShell terminal in the project root. This removes installed dependencies only; it retains source, `.env`, indexed data and backups. Confirm each selected path deliberately.

```powershell
& {
    Set-Location -LiteralPath (Read-Host 'Full path to the extracted rag-mvp folder (no surrounding quotes)') -ErrorAction Stop
    if (-not (Test-Path -LiteralPath '.\release.json' -PathType Leaf)) { throw 'Select the project root.' }
    foreach ($relative in @('.venv', '.test-venv', 'frontend\node_modules')) {
        if (-not (Test-Path -LiteralPath $relative -PathType Container)) { continue }
        $target = Get-Item -LiteralPath $relative -Force -ErrorAction Stop
        $cursor = $target
        $rootPath = (Get-Location).Path
        while ($cursor -and $cursor.FullName -ne $rootPath) {
            if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Linked directory detected; inspect it separately.' }
            $cursor = $cursor.Parent
        }
        $links = Get-ChildItem -LiteralPath $target.FullName -Recurse -Force -ErrorAction Stop |
            Where-Object { ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 }
        if ($links) { throw 'Nested linked directory detected; inspect it separately.' }
        Write-Host 'Selected dependency directory:' $target.FullName
        Remove-Item -LiteralPath $target.FullName -Recurse -Force -Confirm -ErrorAction Stop
    }
}
```

Recreate native and frontend dependencies using [setup](setup.md). Recreate controlled test dependencies separately using [testing](testing.md). Keep lockfiles and requirements files. Do not use environment removal to clear indexed documents.
