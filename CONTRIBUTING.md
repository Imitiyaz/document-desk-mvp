# Contributing

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](AUTHORS.md).

Review the [AGPL-3.0-only application license](LICENSE-NOTICE.md) before using or contributing derivative work. Submit only work you have permission to contribute under the project license; preserve third-party notices and identify copied code or external license conditions. Set up the application and read the architecture, security and limitations guides.

## Propose a change

Describe the user-visible problem, affected document types, a minimal **synthetic** input, expected source facts and acceptance criteria. Do not upload customer documents, secrets or personal logs to an issue.

For behavior changes, agree scope and compatibility before implementation. Large language-model/workflow changes require a capability experiment and independent evaluation; avoid expanding language rules without tests of the broader failure class.

## Implement

Use a focused branch in your own checkout. Keep your Git identity separate from project authorship attribution. Write comments explaining invariants, assumptions and tradeoffs rather than restating obvious statements.

Preserve source identity, raw-value provenance, missing/zero distinctions, unit compatibility, full calculation populations and conversation boundaries. Parameterize database operations. Treat retrieved text and model output as untrusted input.

## Verify

Run [the applicable test layers](docs/testing.md) and `python tools/check_repository.py`. When updating API contracts, regenerate `docs/openapi.json`. Record skips/fakes explicitly. Inspect complete operands and source associations, not only a final number.

Add regressions for ordinary user payloads, changed conversation order and related negative cases. Use independently checked expected data. Do not loosen assertions or change fixture facts to obtain a passing run.

## Pull request

Use the included PR template. Explain the problem and resulting behavior, design/compatibility impact, validation and limitations. Keep application changes, dependency changes and unrelated formatting separable for review.

Do not include generated environments, indexes, raw reports, model caches, personal setup scripts or private notes. A maintainer reviews and merges; passing CI does not authorize deployment.

See [development lifecycle](docs/development.md) for roles and release gates.
