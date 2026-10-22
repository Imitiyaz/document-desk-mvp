# Documentation index — guides, decisions and all Markdown files

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

Use the [project map](../PROJECT_MAP.md) to browse every source file. This index covers every shipped Markdown document, including templates, fixture notes and the generated category pages. The [README visual tour and diagram index](diagrams.md) collects all figures with links to their authoritative explanations.

## Read by task

- Install and verify: [native setup without Docker](setup.md), [Docker deployment](docker.md), [usage](usage.md), [troubleshooting](troubleshooting.md).
- Understand: [stack and rationale](technology-stack.md), [architecture](../ARCHITECTURE.md), [browser-to-answer journey](journey.md), [pipeline](pipeline.md), [data model](data-model.md), [API](api.md).
- Develop and verify: [development](development.md), [testing](testing.md), [UI walkthrough](ui.md), [screenshots](screenshots.md), [validation](validation.md).
- Operate and assess: [operations and recovery](operations.md), [targeted cleanup](cleanup.md), [data locality](privacy.md), [security](../SECURITY.md), [limitations](limitations.md), [acceptance](acceptance.md), [license](../LICENSE-NOTICE.md).

## Design decisions

Decisions record context, implemented choice, rationale, consequences, verification and reconsideration triggers. They do not approve future dependency changes.

## Guides and root documents

**Table IDX-01 — Guides and root documents.**

| Document | Purpose |
| --- | --- |
| [.github/ISSUE_TEMPLATE/bug_report.md](../.github/ISSUE_TEMPLATE/bug_report.md) | Bug report — reproducible application failure |
| [.github/pull_request_template.md](../.github/pull_request_template.md) | Pull request — behavior, design and verification |
| [ARCHITECTURE.md](../ARCHITECTURE.md) | Document Desk MVP — architecture |
| [AUTHORS.md](../AUTHORS.md) | Authors and attribution |
| [CHANGELOG.md](../CHANGELOG.md) | Changelog |
| [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) | Community conduct |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Contributing |
| [LICENSE-NOTICE.md](../LICENSE-NOTICE.md) | Application license and source availability |
| [PROJECT_MAP.md](../PROJECT_MAP.md) | Project map — find documentation and every source file |
| [README.md](../README.md) | Document Desk MVP — ask your documents, check the answer |
| [SECURITY.md](../SECURITY.md) | Security and privacy |
| [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) | Third-party components and models |
| [backend/tests/fixtures/mvp/README.md](../backend/tests/fixtures/mvp/README.md) | Synthetic document fixtures |
| [docs/acceptance.md](acceptance.md) | Supported scope and acceptance boundaries |
| [docs/api.md](api.md) | HTTP API |
| [docs/cleanup.md](cleanup.md) | Cleanup — remove generated artifacts without losing source or document data |
| [docs/configuration.md](configuration.md) | Configuration reference |
| [docs/data-model.md](data-model.md) | Data, identity and lifecycle |
| [docs/development.md](development.md) | Development and delivery lifecycle |
| [docs/diagrams.md](diagrams.md) | Diagram index and visual conventions |
| [docs/docker.md](docker.md) | Docker Compose — install, verify, preserve and recover a local workspace |
| [docs/extending.md](extending.md) | Extending the application |
| [docs/fixtures.md](fixtures.md) | Synthetic fixture catalog |
| [docs/index.md](index.md) | Documentation index — guides, decisions and all Markdown files |
| [docs/journey.md](journey.md) | Browser-to-answer journey — flow, sequence, data and responsibilities |
| [docs/licensing.md](licensing.md) | Licensing, third-party notices and corresponding source |
| [docs/limitations.md](limitations.md) | Known limitations and deployment readiness |
| [docs/operations.md](operations.md) | Local operations and recovery |
| [docs/pipeline.md](pipeline.md) | Processing and answer flow |
| [docs/privacy.md](privacy.md) | Data locality and privacy in the Document Desk MVP |
| [docs/screenshots.md](screenshots.md) | Desktop screenshots — controlled regression and actual-model demonstrations |
| [docs/setup.md](setup.md) | Native setup — run without Docker and verify the first answers |
| [docs/technology-stack.md](technology-stack.md) | Technology stack, responsibilities and selection rationale |
| [docs/testing.md](testing.md) | Testing and evaluation |
| [docs/troubleshooting.md](troubleshooting.md) | Troubleshooting |
| [docs/ui.md](ui.md) | Document Desk MVP — application walkthrough |
| [docs/usage.md](usage.md) | Using the workspace |
| [docs/validation.md](validation.md) | Verification scope and known limits |

## Decision records

**Table IDX-02 — Decision records.**

| Document | Purpose |
| --- | --- |
| [docs/decisions/chunking-strategy.md](decisions/chunking-strategy.md) | Row-aware chunks with complete source records |
| [docs/decisions/embedding-model-selection.md](decisions/embedding-model-selection.md) | Local embedding adapter |
| [docs/decisions/local-llm-selection.md](decisions/local-llm-selection.md) | Local bounded narrative generation |
| [docs/decisions/pdf-parser-selection.md](decisions/pdf-parser-selection.md) | Complementary PDF extraction |
| [docs/decisions/region-continuation.md](decisions/region-continuation.md) | Disclosed Region continuation |
| [docs/decisions/technology-stack.md](decisions/technology-stack.md) | Small replaceable components |
| [docs/decisions/tooling-version-pinning.md](decisions/tooling-version-pinning.md) | Explicit quality-tool versions |
| [docs/decisions/vector-database-selection.md](decisions/vector-database-selection.md) | Embedded Chroma adapter |

## File catalogs

**Table IDX-03 — File catalogs.**

| Document | Purpose |
| --- | --- |
| [docs/catalog/backend-tests.md](catalog/backend-tests.md) | Backend tests, synthetic fixtures and independent oracles |
| [docs/catalog/backend-tooling.md](catalog/backend-tooling.md) | Backend dependencies and verification utilities |
| [docs/catalog/backend.md](catalog/backend.md) | Backend application and contracts |
| [docs/catalog/delivery.md](catalog/delivery.md) | Deployment, repository checks and release tooling |
| [docs/catalog/documentation.md](catalog/documentation.md) | Documentation, decisions and navigation |
| [docs/catalog/frontend-delivery.md](catalog/frontend-delivery.md) | Frontend build, legal assets and configuration |
| [docs/catalog/frontend-tests.md](catalog/frontend-tests.md) | Browser workflows and answer comparison tools |
| [docs/catalog/frontend.md](catalog/frontend.md) | Frontend application, styles and component tests |
| [docs/catalog/index.md](catalog/index.md) | Complete source-file catalog |
| [docs/catalog/project.md](catalog/project.md) | Project, licensing and repository configuration |

