"""Check that basic arithmetic, lost rows and wrong-sheet citations cannot pass.

Author: Imitiyaz and AI Agent
Project: RAG MVP
Layer: Verification and synthetic fixtures
"""

import copy
import json
from pathlib import Path

from app.api.schemas import QueryRequest
from app.structured.engine import table_answer
from tools.quality_recheck import validate_case


def specimen():
    case = {
        "request": {"source_file": "source.xlsx"},
        "expected": {
            "status": "answered",
            "records": [["Sheet", 2, "Amount", "0.1"], ["Sheet", 3, "Amount", "0.2"]],
            "result": {"Amount": "0.3"},
        },
    }
    rows = [
        {
            "sheet_or_page": "Sheet",
            "row_or_location": r,
            "values": {"Amount": v},
            "cell_origins": {"Amount": f"A{r}"},
            "merged_fields": [],
        }
        for r, v in [(2, "0.1"), (3, "0.2")]
    ]
    answer = table_answer(
        QueryRequest(question="Sum Amount", fields=["Amount"], operation="sum"),
        "source.xlsx",
        {"rows": rows, "text_blocks": []},
    )
    return case, answer.model_dump()


def test_independent_exact_oracle_accepts_correct_source_and_sum():
    case, body = specimen()
    assert validate_case(case, body) == []


def test_validator_rejects_simple_wrong_sum_and_omitted_source_cell():
    case, body = specimen()
    wrong = copy.deepcopy(body)
    wrong["calculation"]["result"]["Amount"] = "0.31"
    assert validate_case(case, wrong)
    missing = copy.deepcopy(body)
    missing["records"].pop()
    assert validate_case(case, missing)
    wrong = copy.deepcopy(body)
    wrong["records"][0]["values"]["Amount"] = "0.01"
    assert validate_case(case, wrong)
    wrong_pair = copy.deepcopy(body)
    wrong_pair["answer"] = wrong_pair["answer"].replace("Amount: 0.1", "Amount: 0.2", 1)
    assert validate_case(case, wrong_pair)
    wrong_text = copy.deepcopy(body)
    wrong_text["answer"] = wrong_text["answer"].replace("Amount = 0.3", "Amount = 0.31")
    assert validate_case(case, wrong_text)
    wrong = copy.deepcopy(body)
    wrong["citations"][0]["sheet_or_page"] = "Wrong Sheet"
    assert validate_case(case, wrong)


def test_frozen_golden_cases_are_unique_and_include_both_lookup_and_broad_queries():
    path = Path(__file__).parents[1] / "fixtures/quality/cases.json"
    cases = json.loads(path.read_text(encoding="utf-8-sig"))["cases"]
    assert len(cases) == 16
    assert len({c["id"] for c in cases}) == 16
    assert cases[0]["request"]["question"] == "What was the Q3 revenue for North?"
    assert cases[1]["request"]["question"] == "What was the Q3 revenue?"
