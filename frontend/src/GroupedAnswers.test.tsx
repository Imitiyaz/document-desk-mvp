/* SPDX-License-Identifier: AGPL-3.0-only */
/**
 * Verify GroupedAnswers behavior.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import AnswerContent from "./AnswerContent";
import type { Answer } from "./api";

function specimen(): Answer {
  return {
    status: "incomplete",
    execution_path: "structured",
    answer: "",
    answer_items: [],
    records: [],
    citations: [],
    unresolved_citation_numbers: [],
    coverage: {},
    calculation: null,
    warnings: [],
    timings_seconds: {},
    model: null,
    grouped_results: [
      {
        scope: "Whole file",
        label: "Overall",
        entities: [],
        status: "incomplete",
        answer: "315,000 available-value subtotal",
        record_numbers: [1, 2, 3, 4],
        missing_entities: [],
        calculation: {
          operation: "sum",
          partial: true,
          result: { "Q3 Revenue": "315000" },
          unit: "",
          operands: [],
          excluded_cells: [
            {
              number: 7,
              field: "Q3 Revenue",
              cell: "B4",
              reason: "missing_value",
              source: {
                source_file: "sales.xlsx",
                sheet_or_page: "Sparse Data",
                row_or_location: 4,
              },
            },
          ],
        },
      },
      {
        scope: "Merged Region",
        label: "East + West",
        entities: ["East", "West"],
        status: "no_evidence",
        answer: "No matching records",
        record_numbers: [],
        missing_entities: ["East", "West"],
        calculation: null,
      },
      {
        scope: "Sparse Data",
        label: "North + South",
        entities: ["North", "South"],
        status: "incomplete",
        answer: "83,000; no South record",
        record_numbers: [5, 6],
        missing_entities: ["South"],
        calculation: {
          operation: "sum",
          partial: true,
          result: { "Q3 Revenue": "83000" },
          unit: "",
          operands: [],
        },
      },
    ],
  };
}

test("separates overall, missing values and absent entities without inventing zero", () => {
  render(<AnswerContent answer={specimen()} />);
  const rows = within(screen.getByRole("table")).getAllByRole("row");
  expect(within(rows[1]).getByText("315,000")).toBeVisible();
  expect(within(rows[1]).getByText(/Missing Sparse Data \/ B4/)).toBeVisible();
  expect(
    within(rows[2]).getByText(/No matching source records; no zero inferred/),
  ).toBeVisible();
  expect(within(rows[3]).getByText("83,000")).toBeVisible();
  expect(
    within(rows[3]).getByText("No records for South; contribution unknown."),
  ).toBeVisible();
});

test("group citations open the correct evidence even from a history turn", () => {
  render(
    <>
      <AnswerContent answer={specimen()} prefix="turn-1-" />
      <details data-testid="evidence">
        <summary>Evidence</summary>
        <li id="turn-1-citation-1" tabIndex={-1}>
          Original source cell
        </li>
      </details>
    </>,
  );
  fireEvent.click(
    screen.getByRole("link", { name: "View source 1 for Whole file Overall" }),
  );
  expect(screen.getByTestId("evidence")).toHaveAttribute("open");
  expect(screen.getByText("Original source cell")).toHaveFocus();
});

test("grouped decimals preserve all fractional digits and source text stays literal", () => {
  const answer = specimen();
  answer.grouped_results![0].label = '<img src=x onerror="alert(1)">';
  answer.grouped_results![0].calculation!.result = { Amount: "123456.123456" };
  const { container } = render(<AnswerContent answer={answer} />);
  expect(screen.getByText("123,456.123456")).toBeVisible();
  expect(container.querySelector("img")).toBeNull();
});

test("group operand detail starts collapsed and reveals original cells", () => {
  const answer = specimen();
  answer.grouped_results![0].calculation!.operands = [
    {
      number: 1,
      values: { "Q3 Revenue": "45000" },
      cell_references: { "Q3 Revenue": "B2" },
      source: {
        source_file: "sales.xlsx",
        sheet_or_page: "Merged Region",
        row_or_location: 2,
      },
    },
  ];
  render(<AnswerContent answer={answer} />);
  const text = screen.getByText(
    /Merged Region \/ row 2: Q3 Revenue: 45000 \(B2\)/,
  );
  expect(text).not.toBeVisible();
  fireEvent.click(screen.getAllByText("View this group’s calculation")[0]);
  expect(text).toBeVisible();
});

function contributors(): Answer {
  const answer = specimen();
  answer.coverage.group_field = "Region";
  answer.grouped_results![2].contributions = [
    {
      entity: "North",
      status: "answered",
      record_numbers: [5, 6],
      missing_cells: [],
      calculation: {
        operation: "sum",
        result: { "Q3 Revenue": "83000" },
        unit: "",
        partial: false,
      },
    },
    {
      entity: "South",
      status: "no_evidence",
      record_numbers: [],
      missing_cells: [],
      calculation: null,
    },
  ];
  answer.grouped_results!.push({
    scope: "Sparse Data",
    label: "East + West",
    entities: ["East", "West"],
    status: "incomplete",
    answer: "63,000; East missing",
    record_numbers: [7, 8, 9],
    missing_entities: [],
    calculation: {
      operation: "sum",
      result: { "Q3 Revenue": "63000" },
      unit: "",
      partial: true,
    },
    contributions: [
      {
        entity: "East",
        status: "incomplete",
        record_numbers: [7],
        calculation: null,
        missing_cells: [{ number: 7, field: "Q3 Revenue", cell: "B4" }],
      },
      {
        entity: "West",
        status: "answered",
        record_numbers: [8, 9],
        missing_cells: [],
        calculation: {
          operation: "sum",
          result: { "Q3 Revenue": "63000" },
          unit: "",
          partial: false,
        },
      },
    ],
  });
  return answer;
}

test("contributor details visibly distinguish missing revenue from an absent region", () => {
  render(<AnswerContent answer={contributors()} />);
  const ew = screen.getByRole("list", {
    name: "Region contributions for Sparse Data East + West",
  });
  const regions = within(ew).getAllByRole("listitem");
  expect(regions[0]).toHaveTextContent(
    "East: Missing in source; contribution unknown, not zero.",
  );
  expect(regions[0]).toHaveTextContent("Q3 Revenue missing at B4.");
  expect(regions[1]).toHaveTextContent("West: Q3 Revenue: 63,000 · Total");
  expect(ew).toBeVisible();
  const ns = screen.getByRole("list", {
    name: "Region contributions for Sparse Data North + South",
  });
  expect(within(ns).getAllByRole("listitem")[1]).toHaveTextContent(
    "South: No matching source records; contribution unknown, not zero.",
  );
});

test("missing-region citation opens the original source in the correct conversation turn", () => {
  render(
    <>
      <AnswerContent answer={contributors()} prefix="turn-2-" />
      <details data-testid="missing-evidence">
        <summary>Source evidence</summary>
        <li tabIndex={-1} id="turn-2-citation-7">
          Sparse Data B4
        </li>
      </details>
    </>,
  );
  fireEvent.click(
    screen.getByRole("link", {
      name: "View source 7 for Sparse Data East + West East",
    }),
  );
  expect(screen.getByTestId("missing-evidence")).toHaveAttribute("open");
  expect(screen.getByText("Sparse Data B4")).toHaveFocus();
});

test("an actual zero contribution is displayed as a recorded total", () => {
  const answer = contributors();
  answer.grouped_results![2].contributions![0].calculation!.result = {
    "Q3 Revenue": "0",
  };
  render(<AnswerContent answer={answer} />);
  const ns = screen.getByRole("list", {
    name: "Region contributions for Sparse Data North + South",
  });
  expect(within(ns).getAllByRole("listitem")[0]).toHaveTextContent(
    "North: Q3 Revenue: 0 · Total",
  );
});
