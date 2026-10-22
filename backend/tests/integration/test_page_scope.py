"""Page facts independent of application parsing and arithmetic.

Author: Imitiyaz and AI Agent
"""

from __future__ import annotations

import pytest

from tests.integration.test_intent import ask, conversation
from tests.integration.test_intent import world as world

P1 = [
    ("page_1", "table_1_row_1", "BOLT-A", "10"),
    ("page_1", "table_1_row_2", "NUT-B", "6"),
]
P3 = [
    ("page_3", "table_1_row_1", "BOLT-A", "4"),
    ("page_3", "table_1_row_2", "NUT-B", "8"),
]


def assert_population(body, expected, total):
    assert body["status"] == "answered", body["answer"]
    assert body["calculation"]["result"] == {"Quantity": total}
    assert body["calculation"]["unit"] == "pcs"
    assert sorted(
        (
            r["sheet_or_page"],
            r["row_or_location"],
            r["values"]["Product"],
            r["values"]["Quantity"],
        )
        for r in body["records"]
    ) == sorted(expected)
    assert sorted(
        (
            o["source"]["sheet_or_page"],
            o["source"]["row_or_location"],
            o["values"]["Quantity"],
        )
        for o in body["calculation"]["operands"]
    ) == sorted((s, r, v) for s, r, _, v in expected)
    assert sorted(
        (c["sheet_or_page"], c["row_or_location"]) for c in body["citations"]
    ) == sorted((s, r) for s, r, _, _ in expected)
    assert body["model"] is None


@pytest.mark.parametrize("alias", ["page 1", "page_1", "page-1", "PAGE 1", "page 01"])
def test_page_alias_selects_only_requested_operands(world, alias):
    b = ask(
        world,
        "operations.pdf",
        f"What is the total quantity of NUT-B and BOLT-A in {alias}?",
    )
    assert_population(b, P1, "16")
    assert b["coverage"]["resolved_scopes"] == ["page_1"]
    assert not b["clarification_options"]


@pytest.mark.parametrize("alias", ["page 3", "page_3", "page-3"])
def test_page_three_is_twelve(world, alias):
    assert_population(
        ask(
            world, "operations.pdf", f"Total Quantity for BOLT-A and NUT-B on {alias}?"
        ),
        P3,
        "12",
    )


@pytest.mark.parametrize(
    "alias",
    [
        "page 99",
        "page_99",
        "page-99",
        "page 0",
        "page 2",
        "page 4",
        "pages 1 to 3",
        "pages 1-3",
        "page -1",
        "page 1.5",
        "page 1a",
        "page two",
    ],
)
def test_unavailable_tableless_or_malformed_page_never_broadens(world, alias):
    b = ask(world, "operations.pdf", f"Total Quantity for NUT-B and BOLT-A in {alias}?")
    assert b["status"] == "clarification_required"
    assert not b["records"] and not b["citations"] and b["calculation"] is None
    assert not world[1].llm.prompts


def test_confirmation_and_scope_switch_keep_population_and_replace_question(world):
    ctx = conversation(world, "operations.pdf")

    def turn(q):
        b = ask(world, "operations.pdf", q, **ctx)
        ctx["context_token"] = b["context_token"]
        return b

    assert_population(
        turn("What is the total quantity of NUT-B and BOLT-A in page 1?"), P1, "16"
    )
    assert_population(turn("Use source records"), P1, "16")
    b = turn("page_3")
    assert_population(b, P3, "12")
    assert "page_1" not in b["resolved_question"]
    assert "page 1" not in b["resolved_question"]
    assert_population(turn("And page 1?"), P1, "16")
    b = turn("page 99")
    assert b["status"] == "clarification_required" and not b["records"]
    assert_population(turn("page 3"), P3, "12")


def test_new_explicit_scope_overrides_stale_refinement_and_file_scope_resets(world):
    ctx = conversation(world, "operations.pdf")
    b = ask(
        world,
        "operations.pdf",
        "Total Quantity for NUT-B and BOLT-A in page 1?",
        sheet_or_page="page_3",
        **ctx,
    )
    assert_population(b, P1, "16")
    b = ask(
        world,
        "operations.pdf",
        "Total Quantity for NUT-B and BOLT-A in the file?",
        context_token=b["context_token"],
        **ctx,
    )
    assert b["status"] == "clarification_required"
    b = ask(
        world,
        "operations.pdf",
        "Use source records",
        context_token=b["context_token"],
        **ctx,
    )
    assert_population(b, P1 + P3, "28")


def test_multiple_pages_keep_both_after_confirmation(world):
    ctx = conversation(world, "operations.pdf")
    b = ask(
        world,
        "operations.pdf",
        "Total Quantity for NUT-B and BOLT-A in page 1 and page 3?",
        **ctx,
    )
    assert b["status"] == "clarification_required"
    assert b["coverage"]["resolved_scopes"] == ["page_1", "page_3"]
    assert_population(
        ask(
            world,
            "operations.pdf",
            "Use source records",
            context_token=b["context_token"],
            **ctx,
        ),
        P1 + P3,
        "28",
    )


def test_per_product_breakdown_uses_only_page_one(world):
    b = ask(
        world,
        "operations.pdf",
        "Total Quantity for each Product and overall in page 1?",
    )
    assert b["status"] == "answered", b["answer"]
    assert [
        (g["label"], g["calculation"]["result"]["Quantity"])
        for g in b["grouped_results"]
    ] == [("Overall", "16"), ("BOLT-A", "10"), ("NUT-B", "6")]
    assert {r["sheet_or_page"] for r in b["records"]} == {"page_1"}
