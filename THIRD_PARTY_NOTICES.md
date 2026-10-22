# Third-party components and models

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](AUTHORS.md).

The source archive contains application/test source and synthetic fixtures. It does not bundle Python/npm package distributions or model weights. Installation and deployment can still carry obligations under their licenses.

## Components requiring particular attention


**Table THIRDPARTYNO-T01 — Components requiring particular attention.**

| Component | Publisher reference | Review concern |
| --- | --- | --- |
| PyMuPDF / MuPDF | [PyMuPDF licensing](https://pymupdf.io/licensing) and [project license](https://github.com/pymupdf/PyMuPDF/blob/main/COPYING) | AGPL/commercial licensing paths; evaluate the intended integration, distribution and service use before choosing the project's license or deploying |
| Llama 3.1 model | [Meta Llama 3.1 license](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/LICENSE) | Custom model license and associated use conditions; not inherited from the Python application |
| BAAI/bge-base-en-v1.5 | [Model card](https://huggingface.co/BAAI/bge-base-en-v1.5) | Review the selected model revision, card/license and download terms |
| Ollama | [Official repository](https://github.com/ollama/ollama) | Engine and installed model licenses are distinct |

This is an attention list, not a complete software bill of materials or legal clearance. Check the actual resolved versions and their notices, including transitive/native libraries.

## Dependency inventory

Python direct versions are listed in `backend/requirements-*.txt`. npm resolution is recorded in `frontend/package-lock.json`. Direct Python pins are not a transitive hash lock, and platform/native wheels can differ.

For a release, produce an inventory of the actual environment and review its license/vulnerability findings. Keep the inventory free of local credentials and private host details. Do not copy a third-party license into a project-wide license file as if it licensed the whole application.

## Fixtures

Bundled spreadsheet/PDF test files are synthetic. Some intentionally contain untrusted instructions or missing/ambiguous values to exercise failure behavior. They are not third-party business records or reliable general-domain facts.

## Distribution policy

Application license: AGPL-3.0-only. Preserve upstream notices; do not apply the application license to independently licensed model weights. The default integration uses a separately installed Ollama service. No model weights, npm/Python distributions or prebuilt containers are included in the source ZIP.

The Docker build adds NGINX as a static-file server/reverse proxy and uses official Python/Node/NGINX base images. These deployment components retain their licenses. Base tags and transitive resolver results are not immutable locks: record actual image digests and resolved packages when distributing built images. Review the contents and corresponding-source requirements of every image before publishing it.

Built with Llama when using the configured Llama 3.1 model. Its Community License, attribution and acceptable-use terms remain applicable separately. Operators selecting another model must review that model's terms and update the displayed model attribution accordingly.
