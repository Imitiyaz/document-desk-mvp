"""Exact readable formatting must preserve precision, signs, IDs and literals.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

import pytest

from app.generation.answer_presenter import readable_value


@pytest.mark.parametrize(
    "raw,literal,expected",
    [
        (None, False, "Missing in source"),
        ("45000", False, "45,000"),
        ("1234.0001", False, "1,234.0001"),
        ("-0.0500", False, "-0.0500"),
        ("+1234.00", False, "+1,234.00"),
        ("00123", False, "00123"),
        ("12345", True, "12345"),
        ("2027-01-15", False, "2027-01-15"),
        ("NA", False, "NA"),
        ("USD 10", False, "USD 10"),
        ("[999]", False, "［999］"),
    ],
)
def test_readable_values_preserve_saved_source_meaning(raw, literal, expected):
    assert readable_value(raw, literal=literal) == expected


@pytest.mark.parametrize(
    "field", ["Product Code", "productCode", "product_code", "Account ID", "Year"]
)
def test_numeric_identifiers_keep_literal_digits_in_answer_and_independent_check(field):
    from app.api.schemas import EvidenceRecord
    from app.generation.answer_presenter import record_statement
    from tools.presentation_checks import shown

    record = EvidenceRecord(
        number=1,
        source_file="codes.xlsx",
        sheet_or_page="Codes",
        row_or_location=2,
        values={"Name": "North", field: "12345", "Currency": "USD"},
    )
    assert record_statement(record, [field]) == f"North — {field}: 12345"
    assert shown("12345", field) == "12345"
