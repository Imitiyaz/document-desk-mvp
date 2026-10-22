"""Independent arithmetic, unit, missing-value and scope counterexamples.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from decimal import Decimal

import pytest

from app.api.schemas import QueryRequest
from app.structured.engine import number, table_answer


@pytest.mark.parametrize(
    "value,expected,unit",
    [
        ("45,000", "45000", ""),
        ("0.10", "0.10", ""),
        (-12, "-12", ""),
        ("(12.50)", "-12.50", ""),
        ("$1,234.50", "1234.50", "$"),
        ("USD 12.3", "12.3", "USD"),
        ("12%", "12", "%"),
        ("1e3", "1000", ""),
    ],
)
def test_numeric_parser_retains_exact_decimal_and_unit(value, expected, unit):
    assert number(value) == (Decimal(expected), unit)


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
        "ORD-1001",
        "2027-01-15",
        "1,23",
        "NaN",
        "Infinity",
        "1e999999999",
        "1e-9999999",
        "€12 USD",
        "N/A",
        "",
    ],
)
def test_dates_identifiers_invalid_units_and_unbounded_numbers_are_not_operands(value):
    assert number(value) is None


def doc(values, extra=None):
    rows = []
    for i, value in enumerate(values, 2):
        data = {"Entity": f"E{i}", "Amount": value}
        if extra is not None:
            data["Next Amount"] = extra[i - 2]
        rows.append(
            {
                "sheet_or_page": "Table",
                "row_or_location": i,
                "values": data,
                "cell_origins": {
                    "Entity": f"A{i}",
                    "Amount": f"B{i}",
                    "Next Amount": f"C{i}",
                },
                "merged_fields": [],
            }
        )
    return {"rows": rows, "text_blocks": []}


def answer(document, **options):
    return table_answer(
        QueryRequest(
            question="Amount",
            source_file="x.xlsx",
            sheet_or_page="Table",
            fields=["Amount"],
            **options,
        ),
        "x.xlsx",
        document,
    )


def test_exact_decimal_sum_with_negative_operands():
    b = answer(doc(["0.10", "0.20", "-0.05"]), operation="sum")
    assert b.calculation["result"] == {"Amount": "0.25"}
    assert [x["values"]["Amount"] for x in b.calculation["operands"]] == [
        "0.1",
        "0.2",
        "-0.05",
    ]


def test_large_decimal_sum_does_not_use_28_digit_default_context():
    b = answer(
        doc(["1000000000000000000000000.123456789012", "0.000000000001"]),
        operation="sum",
    )
    assert b.calculation["result"] == {
        "Amount": "1000000000000000000000000.123456789013"
    }


def test_mixed_currency_and_non_numeric_values_are_not_summed():
    for values in (["USD 10", "EUR 20"], ["USD 10", "20"], ["not a number", "20"]):
        b = answer(doc(values), operation="sum")
        assert b.status == "clarification_required"
        assert b.calculation is None
        assert len(b.records) == 2


def test_duplicate_values_are_counted_as_distinct_rows():
    b = answer(doc(["45", "45"]), operation="sum")
    assert b.calculation["result"] == {"Amount": "90"}
    assert len(b.citations) == len(b.records) == 2


def test_tied_minimum_retains_both_source_references():
    b = answer(doc(["10", "10", "20"]), operation="minimum")
    assert b.calculation["result"] == {"Amount": "10"}
    assert "matching source records: [1], [2]" in b.answer


def test_zero_baseline_and_missing_operand_withhold_percentage():
    for values in ([0, 10], [None, 10]):
        b = table_answer(
            QueryRequest(
                question="Growth",
                fields=["Amount", "Next Amount"],
                operation="growth_percent",
                sheet_or_page="Table",
            ),
            "x.xlsx",
            doc(values, [5, 20]),
        )
        assert b.status == "incomplete"
        assert b.calculation is None


def test_direction_and_percentage_are_explicit_and_exact():
    b = table_answer(
        QueryRequest(
            question="Percentage growth",
            fields=["Amount", "Next Amount"],
            operation="growth_percent",
            sheet_or_page="Table",
        ),
        "x.xlsx",
        doc([100, 200], [110, 240]),
    )
    assert b.calculation["result"] == {"1": "10", "2": "20"}
    b = table_answer(
        QueryRequest(
            question="Change",
            fields=["Next Amount", "Amount"],
            operation="increase",
            sheet_or_page="Table",
        ),
        "x.xlsx",
        doc([100], [110]),
    )
    assert b.calculation["result"] == {"1": "-10"}


def test_record_limit_requires_narrowing_instead_of_silent_truncation():
    b = answer(doc(range(25001)), operation="lookup")
    assert b.status == "clarification_required"
    assert b.coverage["matched_records"] == 25001
    assert b.records == []


def test_unknown_explicit_filters_return_no_evidence():
    b = answer(doc([10, 20]), filters={"Entity": "x' OR 1=1 --"})
    assert b.status == "no_evidence"
    assert b.records == []


@pytest.mark.parametrize(
    "value,query,expected",
    [
        (-1, "1", False),
        (-1, "-1", True),
        ("12%", "12", False),
        ("USD 12", "EUR 12", False),
        (None, "None", False),
        ("ORD-1001", "ORD1001", False),
        ("North", " north ", True),
    ],
)
def test_equality_preserves_signs_units_missing_cells_and_identifiers(
    value, query, expected
):
    from app.structured.engine import cell_equal

    assert cell_equal(value, query) is expected


def test_missing_requested_quarter_does_not_return_partial_fields_as_full_answer():
    document = doc([10])
    document["rows"][0]["values"] = {"Q3 Revenue": 10}
    result = table_answer(
        QueryRequest(question="Q3 revenue and Q2 revenue", sheet_or_page="Table"),
        "x.xlsx",
        document,
    )
    assert result.status == "clarification_required"
    assert result.records == []


def test_identifier_leading_zeros_are_not_collapsed_by_equality():
    from app.structured.engine import cell_equal

    assert not cell_equal("0001", "1")
    assert cell_equal("0001", "0001")


def test_very_large_percentage_result_is_rendered_without_default_context_overflow():
    b = table_answer(
        QueryRequest(
            question="Percentage growth",
            fields=["Amount", "Next Amount"],
            operation="growth_percent",
            sheet_or_page="Table",
        ),
        "x.xlsx",
        doc(["0.000000000001"], ["1000000000000000000000000"]),
    )
    assert b.status == "answered"
    assert b.calculation["result"] == {"1": "99999999999999999999999999999999999900"}


def test_declared_currency_column_prevents_mixed_currency_sum():
    data = doc([10, 20])
    for row, unit in zip(data["rows"], ["USD", "EUR"], strict=True):
        row["values"]["Currency"] = unit
    b = answer(data, operation="sum")
    assert b.status == "clarification_required"
    assert b.calculation is None


def test_consistent_declared_unit_is_preserved_in_calculation():
    data = doc([10, 20])
    for row in data["rows"]:
        row["values"]["Unit"] = "kg"
    b = answer(data, operation="sum")
    assert b.calculation["result"] == {"Amount": "30"}
    assert b.calculation["unit"] == "kg"


def test_reported_wrong_sum_is_rejected_by_exact_arithmetic_without_asserting_cross_sheet_additivity():
    b = answer(doc([45000, 38000, 22000, 39000]), operation="sum")
    assert b.calculation["result"] == {"Amount": "144000"}
    assert b.calculation["result"] != {"Amount": "140100"}


def test_repeated_entity_label_across_columns_never_silently_adds_an_and_filter():
    data = doc([10, 20])
    data["rows"][0]["values"].update({"Entity": "North", "Category": "North"})
    data["rows"][1]["values"].update({"Entity": "North", "Category": "South"})
    b = table_answer(QueryRequest(question="Amount for North?"), "x.xlsx", data)
    assert b.status == "clarification_required"
    assert b.records == []
    b = table_answer(QueryRequest(question="Amount for North Entity?"), "x.xlsx", data)
    assert [r.values["Amount"] for r in b.records] == ["10", "20"]
