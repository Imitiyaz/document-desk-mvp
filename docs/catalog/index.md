# Complete source-file catalog

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../../AUTHORS.md).

Every shipped file appears exactly once in a category and in [files.json](files.json). Generated reports, environments, user documents, indexes and private review notes are excluded from the source package. No ordinary application file is intentionally undocumented.

**Table CAT-00 — Catalog categories and file counts.**

| Category | Files |
| --- | --- |
| [Project, licensing and repository configuration](project.md) | 25 |
| [Backend application and contracts](backend.md) | 63 |
| [Backend tests, synthetic fixtures and independent oracles](backend-tests.md) | 88 |
| [Backend dependencies and verification utilities](backend-tooling.md) | 20 |
| [Frontend application, styles and component tests](frontend.md) | 15 |
| [Browser workflows and answer comparison tools](frontend-tests.md) | 14 |
| [Frontend build, legal assets and configuration](frontend-delivery.md) | 13 |
| [Documentation, decisions and navigation](documentation.md) | 49 |
| [Deployment, repository checks and release tooling](delivery.md) | 11 |

Regenerate with `python tools/catalog.py`; check drift with `python tools/catalog.py --check`. Descriptions summarize purpose, not every function contract. Implementation details remain in source comments/docstrings and linked design documentation.
