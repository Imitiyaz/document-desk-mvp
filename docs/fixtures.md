# Synthetic fixture catalog

Author: **Imitiyaz**. AI assistance: **AI Agent**. [Attribution](../AUTHORS.md).

These files are test inputs. They contain synthetic examples, not customer/business records. Do not replace expected facts with current model output.


**Table FIXTURES-T01 — Synthetic fixture catalog.**

| Fixture group | Coverage |
| --- | --- |
| sample_sales.xlsx / sample_report.pdf | Basic region lookups, totals, comparisons and exact citations |
| sample_sales_extended.xlsx | Merged labels, sparse cells, duplicate values and wide records |
| sample_report_extended.pdf | Table extraction and narrative text across pages |
| quality_edges.xlsx | Units, currencies, decimals, ties and comparison boundaries |
| quality/cases.json | Independently specified structured acceptance requests and results |
| mvp/quarters.xlsx | Quarter-specific union/comparison and conversation scope |
| mvp/summary-detail.xlsx | Detail/summary double-counting ambiguity |
| mvp/large.xlsx | 640 records, values 1–640, exact sum 205,120 |
| mvp/cross-page.pdf | Two page-level records, values 10 and 20 |
| mvp/narrative.pdf | Distant-page qualifiers and deliberately untrusted document instructions |
| acceptance/shipments.xlsx | Product/unit identity and repeated product records |
| acceptance/hours.xlsx | 7.5, 8.25, missing and zero; subtotal 15.75 |
| acceptance/operations.pdf | Product quantities across pages and a qualified narrative statement |
| acceptance/capacity-100.xlsx / capacity-1000.xlsx | Synthetic size inputs; no general capacity guarantee |
| acceptance/source-data.json | Explicit source facts for that fixture family |

## Extended sales semantics


**Table FIXTURES-T02 — Extended sales semantics.**

| Section | Physical record values |
| --- | --- |
| Merged Region | North 45,000 and 47,000; South 38,000 and 39,000 |
| Sparse Data | North 45,000; blank Region 38,000; East missing revenue; West 41,000; blank Region 22,000 |

Under the application-specific Region continuation policy, Sparse Data's two blank labels can be interpreted as North and West respectively, with their original blank/anchor evidence retained.

With every physical source record explicitly counted:


**Table FIXTURES-T03 — Extended sales semantics.**

| Population | Known numeric result |
| --- | --- |
| Merged Region | 169,000 |
| Sparse Data | 146,000 available-value subtotal |
| Whole file | 315,000 available-value subtotal |
| North, whole file | 175,000 |
| South, whole file | 77,000 |
| East + West, whole file | 63,000 available-value subtotal; East missing |

These are fixture-specific physical-record expectations. They do not establish that similarly named sheets in an arbitrary business workbook are economically additive.

Fixture generators are available for the original sample and edge families. Some other binary inputs are committed reference fixtures. Review changes to binary inputs and expected facts together; preserve byte identity when only documenting a release.
