"""Generates the synthetic fixture files used by the loader test suite.

These fixtures are small, synthetic, and committed to git alongside this
script (see docs/testing.md § Key Conventions) -- they are not real user
documents, so committing them doesn't violate the data/raw gitignore rule.

Run this manually only if a fixture needs to be regenerated:
    python tests/fixtures/generate_fixtures.py

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

FIXTURES_DIR = Path(__file__).parent


def generate_sample_sales_xlsx() -> None:
    """A workbook with two data sheets and one deliberately empty sheet,
    including a row with a blank cell -- to exercise NaN handling."""
    q3_sales = pd.DataFrame(
        {
            "Region": ["North", "South", "East", "West"],
            "Q3 Revenue": [45000, 38000, 41000, None],  # None -> exercises NaN handling
            "Q4 Revenue": [52000, 39500, 44000, 47000],
        }
    )
    q4_notes = pd.DataFrame(
        {
            "Region": ["North", "South"],
            "Comment": ["Strong growth", "Flat quarter"],
        }
    )
    empty_sheet = pd.DataFrame()

    output_path = FIXTURES_DIR / "sample_sales.xlsx"
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        q3_sales.to_excel(writer, sheet_name="Q3 Sales", index=False)
        q4_notes.to_excel(writer, sheet_name="Q4 Notes", index=False)
        empty_sheet.to_excel(writer, sheet_name="Empty Sheet", index=False)

    print(f"Wrote {output_path}")


def generate_sample_report_pdf() -> None:
    """A one-page PDF with narrative text followed by a bordered table --
    pdfplumber detects bordered tables reliably, which is what we want
    to exercise here."""
    output_path = FIXTURES_DIR / "sample_report.pdf"
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Quarterly Regional Sales Report", styles["Title"]))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(
        Paragraph(
            "This report summarizes regional sales performance for the "
            "third quarter. Overall revenue grew compared to the prior "
            "quarter, driven primarily by strong performance in the "
            "North region.",
            styles["BodyText"],
        )
    )
    elements.append(Spacer(1, 0.3 * inch))

    table_data = [
        ["Region", "Q3 Revenue", "Q4 Revenue"],
        ["North", "45000", "52000"],
        ["South", "38000", "39500"],
        ["East", "41000", "44000"],
    ]
    table = Table(table_data, colWidths=[1.8 * inch, 1.8 * inch, 1.8 * inch])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    print(f"Wrote {output_path}")


def generate_sample_sales_extended_xlsx() -> None:
    """A second workbook targeting edge cases the original sample_sales.xlsx
    never exercised: genuine merged cells (not just blank strings), a row
    wide enough to trigger character-budget splitting, unicode/currency
    text, real datetime values, and blanks scattered across multiple
    columns. Added after Stage 6's manual smoke test surfaced a real bug
    (docs/pipeline.md § extraction and cleaning policy #2) that only
    became visible once someone actually read real chunk text -- these
    fixtures exist to give the same category of latent issue a chance to
    surface via automated tests instead of a human eyeballing output.
    """
    output_path = FIXTURES_DIR / "sample_sales_extended.xlsx"

    merged_region = pd.DataFrame(
        {
            "Region": ["North", None, "South", None],
            "Q3 Revenue": [45000, 47000, 38000, 39000],
            "Q4 Revenue": [52000, 53000, 39500, 40500],
        }
    )

    wide_row = pd.DataFrame(
        {
            "Order ID": ["ORD-1001", "ORD-1002"],
            "Customer": ["Acme Corp", "Beta LLC"],
            "Product": ["Widget A", "Widget B"],
            "Category": ["Hardware", "Hardware"],
            "Quantity": [120, 85],
            "Unit Price": [19.99, 24.50],
            "Discount": [0.10, 0.05],
            "Shipping Method": ["Ground", "Express"],
            "Shipping Address": [
                "1200 Industrial Parkway, Suite 400, Springfield",
                "88 Harbor View Drive, Building C, Portland",
            ],
            "Sales Rep": ["J. Alvarez", "M. Chen"],
            "Region": ["North", "West"],
            "Payment Terms": ["Net 30", "Net 45"],
            "Purchase Order Ref": ["PO-77291", "PO-77304"],
            "Notes": [
                "Customer requested expedited handling for the first shipment "
                "due to a downstream production deadline; confirmed with "
                "warehouse that inventory is sufficient to cover this order "
                "plus the recurring monthly replenishment scheduled for next "
                "month. Customer also asked whether the shipping address can "
                "be split across two delivery locations for future orders, "
                "and whether a dedicated account contact can be assigned "
                "given the increase in order volume over the past two quarters.",
                "Recurring order, same terms as previous quarter. Customer asked "
                "about volume discount tiers for orders above 200 units; sales "
                "rep to follow up with pricing sheet before the next renewal "
                "date. Also flagged a possible change to the primary contact "
                "on this account starting next quarter, pending confirmation "
                "from the customer's procurement team, so renewal paperwork "
                "may need to be reissued under a different named contact.",
            ],
            "Account Manager": ["R. Patel", "R. Patel"],
            "Renewal Date": ["2027-01-15", "2027-02-01"],
            "Status": ["Confirmed", "Pending"],
        }
    )

    unicode_and_currency = pd.DataFrame(
        {
            "Client": ["José García", "François Müller", "Åsa Lindqvist"],
            "Amount": ["€45,000", "£3,200", "¥500,000"],
            "Notes": [
                "Client said “great work this quarter” — renewal likely.",
                "Café Müller & Co. — repeat customer since 2024.",
                "Ordered 3× the usual volume 🎉",
            ],
        }
    )

    dates = pd.DataFrame(
        {
            "Region": ["North", "South", "East"],
            "Order Date": pd.to_datetime(["2026-01-15", "2026-02-03", "2026-03-21"]),
            "Amount": [12000, 8500, 15300],
        }
    )

    sparse_data = pd.DataFrame(
        {
            "Region": ["North", None, "East", "West", None],
            "Q3 Revenue": [45000, 38000, None, 41000, 22000],
            "Q4 Revenue": [None, 39500, 44000, None, 25000],
            "Comment": ["Strong", None, None, "Flat", "New account"],
        }
    )

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        merged_region.to_excel(writer, sheet_name="Merged Region", index=False)
        wide_row.to_excel(writer, sheet_name="Wide Row", index=False)
        unicode_and_currency.to_excel(
            writer, sheet_name="Unicode Currency", index=False
        )
        dates.to_excel(writer, sheet_name="Dates", index=False)
        sparse_data.to_excel(writer, sheet_name="Sparse Data", index=False)

        # Apply a REAL openpyxl merge on the "Region" column of the
        # "Merged Region" sheet -- pandas' DataFrame can't express this on
        # its own; this is what makes rows 2-3 and 4-5 a genuine Excel
        # merge, not just two cells that happen to be blank.
        ws = writer.sheets["Merged Region"]
        ws.merge_cells("A2:A3")  # North
        ws.merge_cells("A4:A5")  # South

    print(f"Wrote {output_path}")


def generate_sample_report_extended_pdf() -> None:
    """A second, multi-page PDF targeting edge cases the original
    sample_report.pdf never exercised: a narrative-only page with no
    table at all, a borderless table (no grid lines -- pdfplumber's
    table detection can miss these), and a repeated footer across every
    page (header_footer.py's repeated-line detection has never been
    tested against a genuinely multi-page real file).
    """
    output_path = FIXTURES_DIR / "sample_report_extended.pdf"
    styles = getSampleStyleSheet()
    elements = []

    # Page 1: narrative only, no table.
    elements.append(Paragraph("Annual Company Overview", styles["Title"]))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(
        Paragraph(
            "This document provides a narrative overview of company "
            "performance across all regions for the fiscal year. Growth "
            "was broad-based, with particularly strong momentum in "
            "customer retention and new account acquisition.",
            styles["BodyText"],
        )
    )
    elements.append(PageBreak())

    # Page 2: a table with NO grid lines -- borderless, to test whether
    # pdfplumber's table detection finds it at all.
    elements.append(Paragraph("Regional Breakdown (Detail)", styles["Title"]))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(
        Paragraph(
            "The following figures summarize regional performance for "
            "the current fiscal year.",
            styles["BodyText"],
        )
    )
    elements.append(Spacer(1, 0.3 * inch))
    borderless_table_data = [
        ["Region", "Headcount", "Growth"],
        ["North", "24", "12%"],
        ["South", "18", "6%"],
        ["East", "21", "9%"],
    ]
    borderless_table = Table(
        borderless_table_data, colWidths=[1.8 * inch, 1.8 * inch, 1.8 * inch]
    )
    # Deliberately no GRID style -- no visible lines, unlike sample_report.pdf's table.
    elements.append(borderless_table)
    elements.append(PageBreak())

    # Page 3: a normal bordered table (known-good detection case),
    # combined with the repeated footer to test dedup + footer-stripping
    # interaction together.
    elements.append(Paragraph("Quarterly Detail", styles["Title"]))
    elements.append(Spacer(1, 0.2 * inch))
    elements.append(
        Paragraph(
            "Detailed quarterly figures are provided below for reference.",
            styles["BodyText"],
        )
    )
    elements.append(Spacer(1, 0.3 * inch))
    bordered_table_data = [
        ["Region", "Q1 Revenue", "Q2 Revenue"],
        ["North", "40000", "43000"],
        ["South", "33000", "35500"],
        ["East", "37000", "39000"],
    ]
    bordered_table = Table(
        bordered_table_data, colWidths=[1.8 * inch, 1.8 * inch, 1.8 * inch]
    )
    bordered_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    elements.append(bordered_table)

    def _draw_footer(canvas, doc) -> None:  # noqa: ANN001
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(
            0.75 * inch, 0.5 * inch, f"Acme Corp - Confidential - Page {doc.page}"
        )
        canvas.restoreState()

    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    doc.build(elements, onFirstPage=_draw_footer, onLaterPages=_draw_footer)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    generate_sample_sales_xlsx()
    generate_sample_report_pdf()
    generate_sample_sales_extended_xlsx()
    generate_sample_report_extended_pdf()
