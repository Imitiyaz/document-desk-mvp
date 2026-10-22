# Licensing, third-party notices and corresponding source

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## Application grant

The original application is **AGPL-3.0-only**. Read [LICENSE](../LICENSE) and [LICENSE-NOTICE](../LICENSE-NOTICE.md). Commercial use is permitted under the license; educational positioning is not a noncommercial restriction or exemption. Preserve original notices and record modifications.

## Dependency and model separation

[Third-party notices](../THIRD_PARTY_NOTICES.md) distinguish PyMuPDF/MuPDF, other Python/npm dependencies, Docker base components, Ollama and model weights. Installing a dependency is not relicensing it. Selecting another model requires checking that model's terms. No model weights or third-party package distributions are bundled in this source ZIP.

Imitiyaz is the author and copyright holder for original project contributions. AI-assisted development is credited separately in [Authors and attribution](../AUTHORS.md). Third-party ownership and license terms remain separate.

## Source release and shared instances

Publish the complete preferred-form application source, configuration, interface definitions and build/install scripts for the released version. Do not publish secrets, personal data, indexes or internal discussions to satisfy source obligations; those are different from application source.

Before sharing a networked instance, edit `frontend/public/legal.html` and `source-info.json` to provide a working link to the exact corresponding source, including local modifications, then rebuild. A different upstream release or an invented placeholder URL is insufficient. The local source distribution refers to its accompanying source ZIP. Shared instances require an exact source URL configured by the operator.

## Binary/container distribution

Building images locally and publishing images are different actions. Before distributing images, inventory their actual packages/base-image digests, retain notices, and meet applicable corresponding-source obligations for the distribution. An application source link alone does not necessarily cover every bundled native library. This repository does not automatically push images or provide a blanket clearance of arbitrary downstream builds.

Use the [GNU AGPL text](https://spdx.org/licenses/AGPL-3.0-only.html), [PyMuPDF license](https://github.com/pymupdf/PyMuPDF/blob/main/COPYING), [Ollama license](https://github.com/ollama/ollama/blob/main/LICENSE) and [Llama 3.1 terms](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/LICENSE) as primary references. This is practical release guidance, not a project-specific legal opinion.
