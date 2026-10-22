/* SPDX-License-Identifier: AGPL-3.0-only */
/** Render actual API specimens against independent source facts.
 * Author: Imitiyaz and AI Agent
 */
import { render, screen, within } from "@testing-library/react";
import { expect, test } from "vitest";
import AnswerContent from "./AnswerContent";
import { products, absentProduct, hoursSubtotal } from "./test-fixtures/intent";
test("product totals keep units and separate each product from the grand total", () => {
  render(<AnswerContent answer={products} />);
  const rows = within(screen.getByRole("table")).getAllByRole("row").slice(1);
  expect(rows).toHaveLength(3);
  for (const [i, label, total] of [
    [0, "Overall", "28"],
    [1, "BOLT-A", "14"],
    [2, "NUT-B", "14"],
  ] as const) {
    const cells = within(rows[i]).getAllByRole("cell");
    expect(cells[0]).toHaveTextContent(label);
    expect(cells[1].querySelector("p")?.textContent).toBe(
      `Quantity: ${total} pcs · Total`,
    );
  }
  expect(
    products.grouped_results?.map((g) =>
      g.calculation?.operands?.map((o) => o.values.Quantity),
    ),
  ).toEqual([
    ["10", "6", "4", "8"],
    ["10", "4"],
    ["6", "8"],
  ]);
});
test("an absent product replaces the current grouped answer instead of retaining its evidence", () => {
  const view = render(<AnswerContent answer={products} />);
  expect(screen.getByRole("table")).toBeInTheDocument();
  view.rerender(<AnswerContent answer={absentProduct} />);
  expect(screen.queryByRole("table")).not.toBeInTheDocument();
  expect(
    screen.getByText(
      "No matching Product records were found for 'Apple' in operations.pdf.",
    ),
  ).toBeInTheDocument();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});
test("a partial hours answer keeps its subtotal warning and zero operand", () => {
  render(<AnswerContent answer={hoursSubtotal} />);
  expect(
    screen.getByText(/Available-value subtotal Hours: 15.75 hours/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Missing source cells excluded: 1/),
  ).toBeInTheDocument();
  expect(screen.getByText(/Excluded Work log \/ B4/)).toBeInTheDocument();
  expect(
    hoursSubtotal.calculation?.operands?.map((o) => [
      o.values.Hours,
      o.cell_references?.Hours,
    ]),
  ).toEqual([
    ["7.5", "B2"],
    ["8.25", "B3"],
    ["0", "B5"],
  ]);
});
