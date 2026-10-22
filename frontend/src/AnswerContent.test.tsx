/* SPDX-License-Identifier: AGPL-3.0-only */
/**
 * Verify AnswerContent behavior.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import AnswerContent from "./AnswerContent";
import type { Answer } from "./api";
const base: Answer = {
  status: "answered",
  execution_path: "structured",
  answer: "North — Q3 Revenue: 45,000 [1]",
  answer_items: [
    {
      kind: "record",
      text: "North — Q3 Revenue: 45,000",
      record_number: 1,
      scope: "Merged Region",
      citation_numbers: [1],
    },
  ],
  records: [],
  citations: [],
  unresolved_citation_numbers: [],
  coverage: {},
  calculation: null,
  warnings: [],
  timings_seconds: {},
  model: null,
};
test("renders a readable value with a clickable source instead of a filename/row dump", () => {
  render(<AnswerContent answer={base} />);
  expect(screen.getByText("North — Q3 Revenue: 45,000")).toBeVisible();
  expect(screen.getByRole("heading", { name: "Merged Region" })).toBeVisible();
  expect(screen.getByRole("link", { name: "View source 1" })).toHaveAttribute(
    "href",
    "#citation-1",
  );
});
test("inline reference opens all collapsed ancestors and focuses the specific source", () => {
  render(
    <>
      <AnswerContent answer={base} />
      <details data-testid="evidence">
        <summary>Evidence</summary>
        <details data-testid="references">
          <summary>Sources</summary>
          <ul>
            <li id="citation-1" tabIndex={-1}>
              Original B2
            </li>
          </ul>
        </details>
      </details>
    </>,
  );
  expect(screen.getByText("Original B2")).not.toBeVisible();
  fireEvent.click(screen.getByRole("link", { name: "View source 1" }));
  expect(screen.getByTestId("evidence")).toHaveAttribute("open");
  expect(screen.getByTestId("references")).toHaveAttribute("open");
  expect(screen.getByText("Original B2")).toBeVisible();
  expect(screen.getByText("Original B2")).toHaveFocus();
});
test("large calculated evidence keeps a short answer and an explicit expansion", () => {
  render(
    <>
      <AnswerContent
        answer={{
          ...base,
          answer_items: [
            {
              kind: "calculation",
              text: "Total Revenue: 205,120.",
              citation_numbers: Array.from({ length: 640 }, (_, i) => i + 1),
            },
          ],
        }}
      />
      <details id="answer-evidence">
        <summary>All operands</summary>
      </details>
    </>,
  );
  expect(screen.getByText("Total Revenue: 205,120.")).toBeVisible();
  expect(screen.getAllByRole("link", { name: /View source/ })).toHaveLength(3);
  fireEvent.click(
    screen.getByRole("link", { name: /637 source records in evidence/ }),
  );
  expect(screen.getByText("All operands").closest("details")).toHaveAttribute(
    "open",
  );
});
test("narrative and older responses retain separate paragraphs and literal source text is escaped", () => {
  const { rerender, container } = render(
    <AnswerContent
      answer={{
        ...base,
        answer_items: [],
        answer: "Revenue did not grow by 12%.\nThe outlook remains uncertain.",
      }}
    />,
  );
  expect(container.querySelectorAll("p")).toHaveLength(2);
  expect(screen.getByText("Revenue did not grow by 12%.")).toBeVisible();
  rerender(
    <AnswerContent
      answer={{
        ...base,
        answer_items: [
          {
            kind: "record",
            text: '<img src=x onerror="alert(1)">',
            citation_numbers: [],
          },
        ],
      }}
    />,
  );
  expect(container.querySelector("img")).toBeNull();
  expect(screen.getByText('<img src=x onerror="alert(1)">')).toBeVisible();
});

test("earlier-turn evidence link opens that turn instead of the current answer", () => {
  render(
    <>
      <AnswerContent
        prefix="turn-0-"
        answer={{
          ...base,
          answer_items: [
            {
              kind: "calculation",
              text: "Total Revenue: 10.",
              citation_numbers: [1, 2, 3, 4],
            },
          ],
        }}
      />
      <details id="turn-0-evidence">
        <summary>Earlier evidence</summary>
      </details>
      <details id="answer-evidence">
        <summary>Current evidence</summary>
      </details>
    </>,
  );
  fireEvent.click(
    screen.getByRole("link", { name: /1 source records in evidence/ }),
  );
  expect(
    screen.getByText("Earlier evidence").closest("details"),
  ).toHaveAttribute("open");
  expect(
    screen.getByText("Current evidence").closest("details"),
  ).not.toHaveAttribute("open");
});
