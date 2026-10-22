/**
 * Check API and visible DOM against independently reviewed fixture facts.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
/** Reviewed source-cell expectations, independent of the API calculation code. */
import { expect, type Page } from "@playwright/test";
import type { Answer } from "../src/api";

const physical = [
  ["Merged Region", 2, "North", "45000"],
  ["Merged Region", 3, "North", "47000"],
  ["Merged Region", 4, "South", "38000"],
  ["Merged Region", 5, "South", "39000"],
  ["Sparse Data", 2, "North", "45000"],
  ["Sparse Data", 3, "North", "38000"],
  ["Sparse Data", 4, "East", null],
  ["Sparse Data", 5, "West", "41000"],
  ["Sparse Data", 6, "West", "22000"],
] as const;

const expected = [
  ["Whole file", "Overall", "315000", true],
  ["Whole file", "East + West", "63000", true],
  ["Whole file", "North + South", "252000", false],
  ["Merged Region", "Overall", "169000", false],
  ["Merged Region", "East + West", null, null],
  ["Merged Region", "North + South", "169000", false],
  ["Sparse Data", "Overall", "146000", true],
  ["Sparse Data", "East + West", "63000", true],
  ["Sparse Data", "North + South", "83000", true],
] as const;

export async function captureGroups(
  page: Page,
  body: Answer,
  expectedSource: string,
) {
  const answer = page.getByRole("region", { name: "Answer", exact: true });
  const table = answer.getByRole("table", {
    name: "Grouped totals and available-value subtotals",
  });
  const rows = table.locator("tbody tr");
  await expect(rows).toHaveCount(9);
  expect(body.status).toBe("incomplete");
  expect(body.grouped_results).toHaveLength(9);
  expect(body.unresolved_citation_numbers).toEqual([]);
  expect(body.records.every((r) => r.source_file === expectedSource)).toBe(
    true,
  );
  expect(body.citations.every((c) => c.source_file === expectedSource)).toBe(
    true,
  );
  expect(
    body.records.map((r) => [
      r.sheet_or_page,
      r.row_or_location,
      r.values.Region,
      r.values["Q3 Revenue"],
    ]),
  ).toEqual(physical);
  const snapshots = [];
  for (const [index, [scope, label, value, partial]] of expected.entries()) {
    const group = body.grouped_results![index];
    expect([group.scope, group.label]).toEqual([scope, label]);
    expect(group.calculation?.result["Q3 Revenue"] ?? null).toBe(value);
    if (partial !== null) expect(group.calculation?.partial).toBe(partial);
    const row = rows.nth(index);
    const cells = row.locator(":scope > th, :scope > td");
    await expect(cells.nth(0)).toHaveText(scope);
    await expect(cells.nth(1)).toHaveText(label);
    const result = cells.nth(2);
    if (value !== null) {
      await expect(result.locator(":scope > p").first()).toHaveText(
        `Q3 Revenue: ${Number(value).toLocaleString("en-US")} · ${partial ? "Available-value subtotal" : "Total"}`,
      );
    } else
      await expect(result).toContainText(
        "No matching source records; no zero inferred.",
      );
    const selected = physical.filter(
      (r) =>
        (scope === "Whole file" || r[0] === scope) &&
        (label === "Overall" || label.split(" + ").includes(r[2])),
    );
    const numeric = selected.filter((r) => r[3] !== null);
    expect(
      (group.calculation?.operands ?? []).map((o) => [
        o.number,
        o.source?.sheet_or_page,
        o.source?.row_or_location,
        o.values["Q3 Revenue"],
        o.cell_references?.["Q3 Revenue"],
      ]),
    ).toEqual(
      numeric.map((r) => [
        physical.indexOf(r) + 1,
        r[0],
        r[1],
        r[3],
        `B${r[1]}`,
      ]),
    );
    const operandText = await cells
      .nth(3)
      .locator("details p")
      .allTextContents();
    for (const r of numeric)
      expect(
        operandText.some(
          (t) =>
            t.replace(/\s+/g, " ").trim() ===
            `[${physical.indexOf(r) + 1}] ${r[0]} / row ${r[1]}: Q3 Revenue: ${r[3]} (B${r[1]})`,
        ),
      ).toBe(true);
    const entities =
      label === "Overall"
        ? [...new Set(selected.map((r) => r[2]))]
        : label.split(" + ");
    expect(group.contributions?.map((c) => c.entity)).toEqual(entities);
    const contributors = [];
    for (const [i, entity] of entities.entries()) {
      const contribution = group.contributions![i];
      const sourceRows = selected.filter((r) => r[2] === entity);
      const numbers = sourceRows.map((r) => physical.indexOf(r) + 1);
      expect(contribution.record_numbers).toEqual(numbers);
      const values = sourceRows
        .filter((r) => r[3] !== null)
        .map((r) => Number(r[3]));
      const li = result.locator(".contributor-details > li").nth(i);
      await expect(li).toBeVisible();
      if (!sourceRows.length) {
        expect(contribution.status).toBe("no_evidence");
        expect(contribution.calculation).toBeNull();
        await expect(li).toContainText(
          `${entity}: No matching source records; contribution unknown, not zero.`,
        );
      } else if (!values.length) {
        expect(contribution.status).toBe("incomplete");
        expect(contribution.calculation).toBeNull();
        expect(contribution.missing_cells.map((c) => c.cell)).toEqual(["B4"]);
        await expect(li).toContainText(
          `${entity}: Missing in source; contribution unknown, not zero.`,
        );
        await expect(li).toContainText("Q3 Revenue missing at B4.");
      } else {
        const sum = values.reduce((a, b) => a + b, 0);
        expect(contribution.calculation?.result["Q3 Revenue"]).toBe(
          String(sum),
        );
        await expect(li).toContainText(
          `${entity}: Q3 Revenue: ${sum.toLocaleString("en-US")}`,
        );
      }
      expect(
        await li
          .locator("a")
          .evaluateAll((links) =>
            links.map((link) => link.getAttribute("href")),
          ),
      ).toEqual(numbers.map((n) => `#citation-${n}`));
      contributors.push({
        entity,
        text: await li.innerText(),
        sources: numbers,
      });
    }
    snapshots.push({
      scope,
      label,
      result: (await result.innerText()).replace(/\s+/g, " ").trim(),
      contributors,
    });
  }
  // Hidden evidence still has a complete physical source/cell contract.
  expect(body.records.map((r) => r.cell_references["Q3 Revenue"])).toEqual([
    "B2",
    "B3",
    "B4",
    "B5",
    "B2",
    "B3",
    "B4",
    "B5",
    "B6",
  ]);
  expect(
    body.citations.map((c) => [c.number, c.sheet_or_page, c.row_or_location]),
  ).toEqual(physical.map((r, i) => [i + 1, r[0], r[1]]));
  await expect(answer.locator(".answer-evidence")).not.toHaveAttribute("open");
  return {
    groups: snapshots,
    citations: body.citations.map((c) => [
      c.number,
      c.sheet_or_page,
      c.row_or_location,
    ]),
    warnings: body.warnings,
  };
}
