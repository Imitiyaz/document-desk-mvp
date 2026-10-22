/** User-reported intent failures: ordinary UI payloads, real rendered evidence.
 * Author: Imitiyaz and AI Agent
 */
import { test, expect, type Page, type TestInfo } from "@playwright/test";
import type { Answer } from "../src/api";
import { sourceRecordsButtonName, documentLibraryReadyText } from "./control-names";

type Checkpoint = {
  status: string;
  results: [string, string | null][];
  records: [string, string | number, string | null][];
  visible: string;
  visibleResults: string[][];
};
async function upload(page: Page, fixture: string, name: string) {
  await expect(page.locator(".library-caption")).toHaveText(documentLibraryReadyText);
  await expect(page.getByLabel("Upload document")).toBeEnabled();
  const previous = page.getByRole("button", {
    name: `Remove ${name}`,
    exact: true,
  });
  if (await previous.count()) {
    await previous.click();
    await page
      .getByRole("button", { name: "Confirm removal", exact: true })
      .click();
    await expect(previous).toHaveCount(0);
  }
  await page
    .getByLabel("Upload document")
    .setInputFiles("../backend/tests/fixtures/acceptance/" + fixture);
  await expect(page.getByRole("status")).toContainText(`${name} indexed`);
}
async function ask(page: Page, question: string): Promise<Answer> {
  const reply = page.waitForResponse(
    (r) => r.url().endsWith("/query") && r.request().method() === "POST",
  );
  await page.getByLabel("Your question").fill(question);
  await page.getByRole("button", { name: "Find answer" }).click();
  const response = await reply;
  expect(response.status()).toBe(200);
  const body: Answer = await response.json();
  await expect(page.locator(".answer-card .answered-question")).toHaveText(
    `Question: ${body.resolved_question || question}`,
  );
  await expect(page.getByRole("button", { name: "Stop waiting" })).toHaveCount(
    0,
  );
  const request = response.request().postDataJSON();
  expect(request.group_field).toBeUndefined();
  expect(request.entity_groups).toBeUndefined();
  return body;
}
async function capture(
  page: Page,
  body: Answer,
  name: string,
  field: string,
): Promise<Checkpoint> {
  const answer = page.getByRole("region", { name: "Answer", exact: true });
  const visible = (await answer.innerText())
    .replaceAll(name, "<document>")
    .replace(/Server time: [\d.]+ s\./g, "Server time: <timing>.")
    .replace(/\s+/g, " ")
    .trim();
  return {
    status: body.status,
    results: body.grouped_results?.length
      ? body.grouped_results.map((g) => [
          g.label,
          g.calculation?.result[field] ?? null,
        ])
      : [["result", body.calculation?.result[field] ?? null]],
    records: body.records.map((r) => [
      r.sheet_or_page,
      r.row_or_location,
      r.values[field] ?? null,
    ]),
    visible,
    visibleResults: body.grouped_results?.length
      ? await answer
          .getByRole("table", {
            name: "Grouped totals and available-value subtotals",
          })
          .locator("tbody tr")
          .evaluateAll((rows) =>
            rows.map((row) => {
              const cells = row.querySelectorAll("th,td");
              return [
                (cells[1]?.textContent ?? "").trim(),
                (cells[2]?.querySelector("p")?.textContent ?? "")
                  .replace(/\s+/g, " ")
                  .trim(),
              ];
            }),
          )
      : [],
  };
}
async function save(
  info: TestInfo,
  scenario: string,
  checkpoints: Record<string, Checkpoint>,
) {
  await info.attach("intent-contract", {
    body: JSON.stringify(
      {
        scenario,
        project: info.project.name,
        run_id: info.config.metadata.verification_id,
        checkpoints,
      },
      null,
      2,
    ),
    contentType: "application/json",
  });
}

test("absent products and each-product plus overall after actual counting confirmation", async ({
  page,
}, info) => {
  const name = "operations.pdf",
    points: Record<string, Checkpoint> = {};
  await page.goto("/");
  await upload(page, "operations.pdf", name);
  const answer = page.getByRole("region", { name: "Answer", exact: true });
  let b = await ask(page, "What is the quantity of Apple in the file ?");
  expect(b.status).toBe("no_evidence");
  expect(b.records).toEqual([]);
  expect(b.citations).toEqual([]);
  await expect(answer).toContainText("No matching Product records were found");
  await expect(answer).toContainText("Apple");
  points.absent = await capture(page, b, name, "Quantity");
  b = await ask(page, "What Quantity is recorded for BOLT-A?");
  expect(b.records.map((r) => r.values.Quantity)).toEqual(["10", "4"]);
  points.known = await capture(page, b, name, "Quantity");
  b = await ask(
    page,
    "What is the total quantity of the individual products and overall products in the file ?",
  );
  expect(b.status).toBe("clarification_required");
  const response = page.waitForResponse(
    (r) => r.url().endsWith("/query") && r.request().method() === "POST",
  );
  await answer
    .getByRole("button", { name: sourceRecordsButtonName, exact: true })
    .click();
  const reply = await response;
  expect(reply.status()).toBe(200);
  b = await reply.json();
  expect(reply.request().postDataJSON().question).toBe("Use source records");
  await expect(
    answer.getByRole("table", {
      name: "Grouped totals and available-value subtotals",
    }),
  ).toBeVisible();
  expect(
    b.grouped_results?.map((g) => [g.label, g.calculation?.result.Quantity]),
  ).toEqual([
    ["Overall", "28"],
    ["BOLT-A", "14"],
    ["NUT-B", "14"],
  ]);
  const expected = [
    ["page_1", "table_1_row_1", "10"],
    ["page_1", "table_1_row_2", "6"],
    ["page_3", "table_1_row_1", "4"],
    ["page_3", "table_1_row_2", "8"],
  ];
  expect(
    b.records.map((r) => [
      r.sheet_or_page,
      r.row_or_location,
      r.values.Quantity,
    ]),
  ).toEqual(expected);
  expect(b.citations.map((c) => [c.sheet_or_page, c.row_or_location])).toEqual(
    expected.map((r) => r.slice(0, 2)),
  );
  const rows = answer
    .getByRole("table", {
      name: "Grouped totals and available-value subtotals",
    })
    .locator("tbody tr");
  await expect(rows).toHaveCount(3);
  for (const [i, [label, total]] of [
    ["Overall", "28"],
    ["BOLT-A", "14"],
    ["NUT-B", "14"],
  ].entries()) {
    await expect(rows.nth(i)).toContainText(label);
    await expect(rows.nth(i)).toContainText(`Quantity: ${total} pcs · Total`);
  }
  expect(
    b.grouped_results?.map((g) =>
      g.calculation?.operands?.map((o) => [
        o.source?.sheet_or_page,
        o.values.Quantity,
      ]),
    ),
  ).toEqual([
    [
      ["page_1", "10"],
      ["page_1", "6"],
      ["page_3", "4"],
      ["page_3", "8"],
    ],
    [
      ["page_1", "10"],
      ["page_3", "4"],
    ],
    [
      ["page_1", "6"],
      ["page_3", "8"],
    ],
  ]);
  points.grouped = await capture(page, b, name, "Quantity");
  b = await ask(page, "What is the quantity of Apple in the file ?");
  expect(b.status).toBe("no_evidence");
  points.after_confirm = await capture(page, b, name, "Quantity");
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  b = await ask(page, "What is the quantity of Apple in the file ?");
  expect(b.status).toBe("no_evidence");
  points.fresh = await capture(page, b, name, "Quantity");
  b = await ask(page, "Total Quantity for BOLT-A and Apple?");
  expect(b.status).toBe("clarification_required");
  expect(b.calculation).toBeNull();
  await expect(answer).toContainText("BOLT-A");
  await expect(answer).toContainText("Apple");
  points.mixed = await capture(page, b, name, "Quantity");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await save(info, "products", points);
});

test("equivalent totals, absent names, missing cells and zero survive reordered followups", async ({
  page,
}, info) => {
  const name = "hours.xlsx",
    points: Record<string, Checkpoint> = {};
  await page.goto("/");
  await upload(page, "hours.xlsx", name);
  const answer = page.getByRole("region", { name: "Answer", exact: true });
  let b = await ask(page, "What Hours are recorded for Asha totally ?");
  expect(b.calculation?.result.Hours).toBe("15.75");
  expect(b.records.map((r) => r.values.Hours)).toEqual(["7.5", "8.25", "0"]);
  await expect(answer.locator(".readable-answer")).toContainText("15.75 hours");
  points.alias = await capture(page, b, name, "Hours");
  b = await ask(page, "Total hours for Zenzee?");
  expect(b.status).toBe("no_evidence");
  expect(b.citations).toEqual([]);
  await expect(answer).toContainText("Zenzee");
  points.absent = await capture(page, b, name, "Hours");
  b = await ask(page, "And Ben?");
  expect(b.status).toBe("incomplete");
  expect(b.records[0].values.Hours).toBeNull();
  await expect(answer).toContainText("Missing in source");
  points.missing = await capture(page, b, name, "Hours");
  b = await ask(page, "And Asha?");
  expect(b.calculation?.result.Hours).toBe("15.75");
  points.returned = await capture(page, b, name, "Hours");
  b = await ask(page, "What is the sum of Hours?");
  expect(b.status).toBe("incomplete");
  expect(b.calculation?.result.Hours).toBe("15.75");
  expect(b.calculation?.operands?.map((o) => o.values.Hours)).toEqual([
    "7.5",
    "8.25",
    "0",
  ]);
  await expect(answer.locator(".answer-evidence")).not.toHaveAttribute("open");
  await expect(answer.locator(".readable-answer")).toContainText("subtotal");
  points.subtotal = await capture(page, b, name, "Hours");
  await answer
    .getByRole("link", { name: "View source 3", exact: true })
    .first()
    .focus();
  await page.keyboard.press("Enter");
  await expect(answer.locator("#citation-3")).toBeFocused();
  await expect(answer.locator(".answer-evidence")).toHaveAttribute("open", "");
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  b = await ask(page, "Total hours for Asha ?");
  expect(b.calculation?.result.Hours).toBe("15.75");
  points.canonical = await capture(page, b, name, "Hours");
  b = await ask(page, "Hours for Asha excluding Ben?");
  expect(b.status).toBe("clarification_required");
  expect(b.calculation).toBeNull();
  points.qualifier = await capture(page, b, name, "Hours");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await save(info, "hours", points);
});
