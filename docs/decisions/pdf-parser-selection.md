# Complementary PDF extraction

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../../AUTHORS.md).

Decision owner and approver: **Imitiyaz**.

Status: implemented in application 0.3.8; this record explains the current choice and its trade-offs.

## Context and requirements

I use this component in the Document Desk MVP to support local processing, source identity and reproducible behavior. The choice below describes the implementation and its boundaries.

## Decision

Use PyMuPDF for page text and pdfplumber for tables. Carry page, table-row and text locations into evidence.

## Consequences and verification

Two parsers do not guarantee layout fidelity. OCR and arbitrary tables are unsupported; review PyMuPDF licensing. See [pipeline](../pipeline.md).

## Why this decision

PyMuPDF supplies tested page text while pdfplumber supplies table structure. Keeping both preserves baseline extraction and provenance. The application uses the AGPL publication route rather than replacing the parser for a noncommercial license.

## Options and trade-offs

The component fits the current fixtures and adapter contracts. Replacing it requires a representative benchmark, source/operand invariants and a migration/rollback plan. Adding another framework alone does not address factual correctness. See the [stack inventory](../technology-stack.md).

## Future reconsideration triggers

Revisit when an independently demonstrated document format, accuracy target, hardware limit, license requirement or deployment mode cannot be met. Define the acceptance cases before changing the dependency, preserve the old baseline, and compare extraction, correctness, latency/RAM and recovery. Compare proposed changes against explicit acceptance cases before replacing the component.
