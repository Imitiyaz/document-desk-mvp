"""Reject the actual ambiguous presentation and unrelated-citation regressions.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

from typing import Any

from tools.answer_checks import check_fixture_answer


def _citation(number: int, sheet: str, row: int | str) -> dict[str, Any]:
    return {"number": number, "sheet_or_page": sheet, "row_or_location": row}


def test_correct_total_does_not_hide_unlabelled_operand_mapping() -> None:
    body = {
        "answer": "The combined Q3 revenue for North, South, and East is 38000 + 41000 + 45000 = 124000. (Source: [1], [2], [3])",
        "citations": [
            _citation(1, "Q3 Sales", 3),
            _citation(2, "Q3 Sales", 4),
            _citation(3, "Q3 Sales", 2),
        ],
    }
    assert check_fixture_answer("total", body)
    body["answer"] = (
        "North: 45,000 (Source: [3]); South: 38,000 (Source: [1]); East: 41,000 (Source: [2]). Total: 124,000."
    )
    assert check_fixture_answer("total", body) == []


def test_reversed_merged_records_are_flagged() -> None:
    body = {
        "answer": "47000 [1] and 45000 [2]",
        "citations": [
            _citation(1, "Merged Region", 3),
            _citation(2, "Merged Region", 2),
        ],
    }
    assert check_fixture_answer("merged", body)
    body["answer"] = "45000 [2] and 47000 [1]"
    assert check_fixture_answer("merged", body) == []


def test_correct_comparison_cannot_cite_comment_only_sheet() -> None:
    body = {
        "answer": "North, 7000 (52000 - 45000) [3] [4]",
        "citations": [_citation(3, "Q3 Sales", 2), _citation(4, "Q4 Notes", 2)],
    }
    assert check_fixture_answer("comparison", body)
    body["citations"] = [_citation(3, "Q3 Sales", 2)]
    assert check_fixture_answer("comparison", body) == []


def test_wide_date_requires_correct_original_record() -> None:
    body = {
        "answer": "2027-01-15 [1]",
        "citations": [_citation(1, "Wide Row", "3_part2")],
    }
    assert check_fixture_answer("wide", body)
    body["citations"] = [_citation(1, "Wide Row", "2_part2")]
    assert check_fixture_answer("wide", body) == []


def test_total_introductory_names_do_not_hide_labelled_values() -> None:
    body = {
        "answer": (
            "To calculate the combined Q3 revenue for North, South, and East, "
            "we need the relevant values.\n\n"
            "North: Q3 Revenue is 45000 (Source: [6])\n"
            "South: Q3 Revenue is 38000 (Source: [5])\n"
            "East: Q3 Revenue is 41000 (Source: [4])\n\n"
            "Combined Q3 revenue for North, South, and East: "
            "45000 + 38000 + 41000 = 124000"
        ),
        "citations": [
            _citation(6, "Q3 Sales", 2),
            _citation(5, "Q3 Sales", 3),
            _citation(4, "Q3 Sales", 4),
        ],
    }
    assert check_fixture_answer("total", body) == []
    body["answer"] = str(body["answer"]).replace(
        "North: Q3 Revenue is 45000", "North: Q3 Revenue is 38000"
    )
    assert check_fixture_answer("total", body)
