# Using the workspace

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

## First document

Start both servers as described in [setup](setup.md). Upload `backend/tests/fixtures/sample_sales.xlsx` through the document library. Wait until indexing succeeds, select the document and ask:

> What was the Q3 revenue for North in the Q3 Sales sheet?

The sample value is **45,000**, with `Q3 Sales` row 2 / cell B2. Expand evidence to inspect the field, value and physical source. Citation numbers identify records in that answer; they are not permanent document identifiers.

## Lookups and calculations


**Table USAGE-T01 — Lookups and calculations.**

| Question / fixture | Expected interpretation |
| --- | --- |
| “What Quantity is recorded for BOLT-A in January?” / shipments.xlsx | Two separate values, 12 and 7 pcs |
| “Total hours for Asha?” / hours.xlsx | 7.5 + 8.25 + 0 = 15.75 hours |
| “What Hours are recorded for Ben?” / hours.xlsx | Matching record with missing Hours |
| “What is the sum of Hours?” / hours.xlsx | 15.75 available-value subtotal; Ben's blank excluded, not zero |
| “Total hours for Zenzee?” / hours.xlsx | No matching entity evidence |
| “Sum Quantity in page 1” / operations.pdf | 10 + 6 = 16 pcs |

The last three files are in `backend/tests/fixtures/acceptance/`. They contain synthetic data.

For ambiguous cross-sheet/page totals, the application may ask whether every selected physical source record should count. Confirm only if that matches the question. A repeated value on a separate sheet is not automatically a duplicate, nor automatically independent business revenue.

The extended sales fixture deliberately contains overlapping records, merged labels and missing revenue. With the explicit physical-record basis, the known numeric whole-file subtotal is 315,000. This does not prove that the sheets represent additive business populations. [Fixture semantics](fixtures.md) explain the assumptions.

## Follow-ups and scopes

The selected document is the default scope. Optional sheet/page refinements narrow it. Ordinary questions can also mention a source section, such as “in Merged Region” or “on page 3.”

Within a conversation, follow-ups such as “And South?” or “Sum these records” can inherit a recognized metric and scope. The displayed effective question shows what was resolved. If it differs from your intent, refine the question before using the result.

Broader language is not universally understood. Explicit field/filter controls and focused clarification are available. New chat clears request context; it does not remove indexed documents.

## Reading results

- `answered`: the implemented path produced a result; it is not a universal correctness certification.
- `incomplete`: inspect missing values, absent contributors, partial source coverage and subtotal warnings.
- `no_evidence`: no supported result was found under the implemented scope; it does not prove the fact does not exist anywhere.
- `clarification_required`: choose a proposed option or specify the unresolved part.

Evidence may be paginated. A calculation should still expose every operand through its calculation evidence. Compare subject, unit, period, population and source associations, not only the headline number.

## Document controls


**Table USAGE-T02 — Document controls.**

| Control | Effect |
| --- | --- |
| New chat | Starts clean request context for the selected document |
| Remove document | Deletes that document's managed ledger/vector records and invalidates its conversations |
| Reset workspace | Deletes all managed documents and conversations after confirmation |

These actions do not delete original files on your disk or model caches. Keep originals separately. Removal is not a secure-erase guarantee for filesystem backups or storage media.

## Narrative questions

For `operations.pdf`, “Is Orchid production launch approved and when is the next review?” exercises the narrative path. Check both the approval qualifier and review date against page 4.

The current narrative path can select genuine sentences about the wrong entity. An exact source quote and a valid citation therefore do not establish that the answer satisfies the question. See [limitations](limitations.md).
