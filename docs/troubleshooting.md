# Troubleshooting

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## Missing commands


**Table TROUBLESHOOT-T01 — Missing commands.**

| Symptom | Check / action |
| --- | --- |
| Python launcher missing | Finish Python 3.12 installation and reopen the terminal |
| `vite` not recognized | Run `npm ci --include=dev --bin-links=true` in frontend, then check `node_modules/.bin/vite.cmd` on Windows |
| npm EBUSY removing a package | Stop that checkout's frontend/test processes, close file handles and retry installation; do not kill unrelated system processes |
| Missing backend module | Use the repository environment's Python and start from root with `--app-dir backend` |
| `.env` missing | Copy `.env.example` once; do not overwrite an existing local configuration |

Do not install Vite globally or delete the lockfile to fix a local missing dependency. Avoid `npm audit fix --force`; review upgrades and their compatibility instead.

## Ports and startup

If port 8000, 5173 or 11434 is occupied, identify the owning process and whether it is the intended service. Keep one API worker. Playwright deliberately rejects an existing server to avoid testing or deleting the wrong workspace.

The first embedding start may download weights. Check the actual error, network policy and available disk/RAM before repeatedly restarting. `/ready` does not contact Ollama.

## Compose cannot find a configuration file

Do not rebuild from a guessed folder. The project root directly contains `compose.yaml`, `backend` and `frontend`. Rerun [Docker Step 1](docker.md#1-select-the-actual-source-folder-and-check-prerequisites) with your actual extracted root, then use its explicit `--project-directory`, `-f` and `-p` arguments. An inherited `COMPOSE_FILE` or another checkout must not choose a different project. A working `docker run hello-world` proves the engine, not the location of this application's Compose file.

## Upload problems

- 409 duplicate: choose the existing document, or remove that selected version and upload its original again.
- 415 XLS: re-save as XLSX. CSV and other types are not registered in this release.
- 413: inspect file, expanded ZIP, row, column and page limits; do not merely raise all limits.
- 422: inspect corruption, encryption, empty/image-only content or unsupported layout.

Use synthetic reproduction files when reporting parser issues. Do not share a confidential original in a public issue.

## Queries and conversation

Refresh the document catalog after remove/reset or a stale-workspace error. Start a new chat if its context expired or its document changed.

Inspect the resolved question, source scope, missing-data warnings and evidence. A known subtotal is not the same as a complete total. If an unknown entity receives another entity's narrative, treat the answer as unsupported and consult the known limitation.

Changing top_k does not fix a malformed structured population or a wrong-entity answer. Evidence pagination does not change the full calculation operands.

## Narrative generation is slow or falls back

Check host Ollama and the configured model/endpoint separately from `/ready`. Read Request details: `source_grounded_summary` with a model differs from labeled `source_excerpts` / evidence-only fallback. Preserve the exact status, warnings and raw response; do not count correct excerpts as completed model synthesis. An operational LLMConnectionError does not itself identify cold start, timeout or memory as its cause. Avoid repeated simultaneous submissions; the one-worker service serializes operations.

## Test failures

Read the first failing command/log, preserve its artifacts and distinguish infrastructure errors from application assertions. Browser failure can come from missing Chromium/system libraries, incorrect Python selection, occupied ports or actual UI behavior.

Use the exact suite documented in testing. Do not repeat unrelated passing suites without a reason or relax an assertion solely because a new response looks plausible.
