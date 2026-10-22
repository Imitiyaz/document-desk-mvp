/**
 * Exercise real browser journeys in desktop and mobile-emulated viewports.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import { test, expect, type Page } from "@playwright/test";
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { captureGroups } from "./answer-contract";
import type { Answer } from "../src/api";
async function upload(page: Page, fixture: string, name: string) {
  await page.getByLabel("Upload document").setInputFiles({
    name,
    mimeType: "application/octet-stream",
    buffer: await readFile(resolve(`../backend/tests/fixtures/${fixture}`)),
  });
  await expect(page.getByRole("status")).toContainText(`${name} indexed`, {
    timeout: 30000,
  });
}
async function ask(page: Page, question: string) {
  const pending = page.waitForResponse(
    (r) => r.url().endsWith("/query") && r.request().method() === "POST",
  );
  await page.getByLabel("Your question").fill(question);
  await page.getByRole("button", { name: "Find answer" }).click();
  const reply = await pending;
  expect(reply.status()).toBe(200);
  const body: Answer = await reply.json();
  await expect(page.locator(".answer-card .answered-question")).toHaveText(
    `Question: ${body.resolved_question || question}`,
    { timeout: 30000 },
  );
  await expect(page.getByRole("button", { name: "Stop waiting" })).toHaveCount(
    0,
  );
}

test("whole document, all provenance, follow-up, clarification and selective removal", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByLabel("Upload document")).toBeEnabled();
  const name = `review-${info.project.name}.xlsx`;
  await upload(page, "sample_sales_extended.xlsx", name);
  await expect(page.getByText("Refine sources — optional")).toBeVisible();
  await expect(page.locator(".optional-refinements")).not.toHaveAttribute(
    "open",
  );
  await ask(page, "What was the Q3 revenue for North?");
  const answer = page.getByRole("region", { name: "Answer", exact: true });
  await expect(answer.locator(".readable-answer")).toContainText(
    "North has 4 recorded Q3 Revenue values",
  );
  await expect(answer.locator(".readable-answer")).toContainText("45,000");
  await expect(answer.locator(".readable-answer")).toContainText("47,000");
  await expect(answer.locator(".answer-evidence")).not.toHaveAttribute("open");
  await expect(answer.locator("table")).not.toBeVisible();
  await answer
    .getByRole("link", { name: "View source 2", exact: true })
    .click();
  await expect(answer.locator(".answer-evidence")).toHaveAttribute("open", "");
  await expect(answer.locator("#citation-2")).toBeFocused();
  await expect(answer.locator("tbody tr")).toHaveCount(4);
  for (const [i, value] of ["45000", "47000", "45000", "38000"].entries())
    await expect(answer.locator("tbody tr").nth(i)).toContainText(value);
  await answer
    .getByRole("link", { name: "[1] Merged Region", exact: true })
    .click();
  await expect(answer.locator("#citation-1")).toBeVisible();
  await ask(page, "And South?");
  await expect(answer.locator("tbody tr")).toHaveCount(2);
  await expect(
    page.getByRole("region", { name: "Earlier conversation" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  await expect(answer).toHaveCount(0);
  await expect(page.getByRole("option", { name, exact: true })).toBeAttached();
  await ask(page, "What was the Q3 revenue?");
  await expect(answer.locator(".readable-answer")).toContainText(
    "I found 9 Q3 Revenue records",
  );
  await expect(answer.locator(".readable-answer")).toContainText(
    "East — Q3 Revenue: Missing in source",
  );
  await expect(answer.locator(".answer-evidence")).not.toHaveAttribute("open");
  await expect(answer.locator("tbody tr")).toHaveCount(9);
  await expect(
    answer.getByText("Incomplete answer", { exact: true }),
  ).toBeVisible();
  await expect(answer.locator(".answer-evidence .calculation")).toHaveCount(0);
  await ask(page, "Total Q3 revenue");
  await answer
    .getByRole("button", { name: "Merged Region →", exact: true })
    .click();
  await expect(answer.locator(".answer-evidence .calculation")).toContainText(
    "169000",
  );
  await page.reload();
  await expect(page.getByRole("option", { name, exact: true })).toBeAttached();
  await expect(answer).toHaveCount(0);
  const remove = page.getByRole("button", {
    name: `Remove ${name}`,
    exact: true,
  });
  await remove.click();
  await expect(page.getByRole("button", { name: "Keep data" })).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(
    page.getByRole("button", { name: "Confirm removal" }),
  ).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(page.getByRole("button", { name: "Keep data" })).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("alertdialog")).toHaveCount(0);
  await expect(remove).toBeFocused();
  await remove.click();
  await page.getByRole("button", { name: "Confirm removal" }).click();
  await expect(page.getByRole("option", { name, exact: true })).toHaveCount(0);
  await upload(page, "sample_sales_extended.xlsx", name);
  const size = await page.evaluate(() => ({
    width: innerWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(size.scroll).toBeLessThanOrEqual(size.width + 1);
  expect(errors).toEqual([]);
});

test("compatible cross-sheet total, full paged calculation, reset and reupload", async ({
  page,
}, info) => {
  await page.goto("/");
  await expect(page.getByLabel("Upload document")).toBeEnabled();
  const name = `quarters-${info.project.name}.xlsx`;
  await upload(page, "mvp/quarters.xlsx", name);
  const answer = page.getByRole("region", { name: "Answer", exact: true });
  await ask(page, "Combined Revenue for North in Q3 Sales and Q4 Sales");
  await expect(answer.locator(".answer-evidence .calculation")).toContainText(
    "97000",
  );
  await expect(answer.locator("tbody tr")).toHaveCount(2);
  await ask(page, "And South?");
  await expect(answer.locator(".answer-evidence .calculation")).toContainText(
    "78000",
  );
  await upload(page, "mvp/large.xlsx", `large-${info.project.name}.xlsx`);
  await ask(page, "Total Revenue");
  await expect(answer.locator("tbody tr")).toHaveCount(50);
  await expect(answer.locator(".coverage")).toContainText(
    "640 matching records",
  );
  await expect(answer.locator(".answer-evidence .calculation")).toContainText(
    "205120",
  );
  await expect(answer.locator(".readable-answer")).toContainText(
    "Total Revenue: 205,120.",
  );
  await expect(answer.locator(".readable-answer")).not.toContainText(name);
  await answer.locator(".answer-evidence > summary").click();
  await answer.getByRole("button", { name: "Next records" }).click();
  await expect(answer.getByText("Page 2 of 13")).toBeVisible();
  await expect(answer.locator("tbody tr").first()).toContainText("B52");
  await answer
    .getByRole("link", { name: "View source 1", exact: true })
    .click();
  await expect(answer.locator("#citation-1")).toBeVisible();
  await expect(answer.locator(".answer-evidence .calculation")).toContainText(
    "205120",
  );
  await page.getByRole("button", { name: "Reset workspace" }).click();
  await expect(page.getByRole("alertdialog")).toContainText(
    "indexed documents",
  );
  await page.getByRole("button", { name: "Confirm removal" }).click();
  await expect(
    page.getByText("0 indexed documents", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("0 indexed documents", { exact: true }),
  ).toBeVisible();
  await upload(page, "mvp/quarters.xlsx", name);
  await ask(page, "Combined Revenue for North in Q3 Sales and Q4 Sales");
  await expect(answer.locator(".answer-evidence .calculation")).toContainText(
    "97000",
  );
});

test("confirmed physical-record subtotal and explicit sheet change in the same conversation", async ({
  page,
}, info) => {
  await page.goto("/");
  await expect(page.getByLabel("Upload document")).toBeEnabled();
  await upload(
    page,
    "sample_sales_extended.xlsx",
    `sum-scope-${info.project.name}.xlsx`,
  );
  const answer = page.getByRole("region", { name: "Answer", exact: true });
  await ask(page, "What is the SUM of Q3 revenue in the file ?");
  await answer
    .getByRole("button", { name: "Use source records →", exact: true })
    .click();
  await expect(answer.locator(".readable-answer")).toContainText(
    "Available-value subtotal Q3 Revenue: 315,000.",
  );
  await expect(answer.locator(".subtotal-coverage")).toContainText(
    "8 of 9 source records",
  );
  await expect(answer.locator(".readable-answer")).toContainText(
    "Sparse Data / B4",
  );
  await ask(page, "What is the SUM of Q3 revenue in the file ?");
  await answer
    .getByRole("button", { name: "Sparse Data →", exact: true })
    .click();
  await expect(answer.locator(".readable-answer")).toContainText(
    "Available-value subtotal Q3 Revenue: 146,000.",
  );
  await expect(page.getByLabel("Sheet or page")).toHaveValue("");
  await ask(page, "What was the Q3 revenue for north in Merged Region?");
  await expect(answer.locator(".readable-answer")).toContainText("45,000");
  await expect(answer.locator(".readable-answer")).toContainText("47,000");
  await expect(answer.locator("tbody tr")).toHaveCount(2);
  await expect(answer.locator(".resolved-scope")).toHaveText(
    "Source scope used: Merged Region",
  );
  await expect(answer.locator("tbody")).not.toContainText("Sparse Data");
  await ask(page, "And South?");
  await expect(answer.locator(".readable-answer")).toContainText("38,000");
  await expect(answer.locator(".readable-answer")).toContainText("39,000");
  await ask(page, "What was the Q3 revenue in the file ?");
  await expect(answer.locator("tbody tr")).toHaveCount(9);
});

test("compound follow-up keeps Q3, continuation provenance and every file/sheet group", async ({
  page,
}, info) => {
  await page.goto("/");
  await upload(
    page,
    "sample_sales_extended.xlsx",
    `groups-${info.project.name}.xlsx`,
  );
  await ask(page, "What is the SUM of Q3 revenue in the file ?");
  const answer = page.getByRole("region", { name: "Answer", exact: true });
  await answer
    .getByRole("button", { name: "Use source records →", exact: true })
    .click();
  await expect(answer.locator(".readable-answer")).toContainText("315,000");
  await ask(page, "What was the Q3 revenue for north in Merged Region?");
  await ask(page, "Sum these records");
  await expect(answer.locator(".readable-answer")).toContainText("92,000");
  await ask(page, "and South ?");
  await expect(answer.locator(".readable-answer")).toContainText("77,000");
  await ask(
    page,
    "and sum of East and West ? and Sum of North and South ? from the file and from the individual sheets",
  );
  const table = answer.getByRole("table", {
    name: "Grouped totals and available-value subtotals",
  });
  await expect(table).toBeVisible();
  const rows = table.locator("tbody tr");
  await expect(rows).toHaveCount(9);
  const overall = rows
    .filter({
      has: page.getByRole("rowheader", { name: "Whole file", exact: true }),
    })
    .filter({ has: page.getByRole("cell", { name: "Overall", exact: true }) });
  await expect(overall).toContainText("315,000");
  const northSouth = rows
    .filter({
      has: page.getByRole("rowheader", { name: "Whole file", exact: true }),
    })
    .filter({
      has: page.getByRole("cell", { name: "North + South", exact: true }),
    });
  await expect(northSouth).toContainText("252,000");
  const eastWest = rows
    .filter({
      has: page.getByRole("rowheader", { name: "Whole file", exact: true }),
    })
    .filter({
      has: page.getByRole("cell", { name: "East + West", exact: true }),
    });
  await expect(eastWest).toContainText("63,000");
  await expect(eastWest).toContainText("Available-value subtotal");
  await expect(answer.locator(".answer-evidence")).not.toHaveAttribute("open");
  // The first three citations stay concise; open shared evidence for the continuation rows.
  await answer.locator(".answer-evidence > summary").click();
  const sourceRows = answer.locator(".answer-evidence tbody tr");
  await expect(sourceRows.nth(5)).toContainText("North");
  await expect(sourceRows.nth(5)).toContainText(
    "Original cell blank · continued from A2 (row 2)",
  );
  await expect(sourceRows.nth(8)).toContainText(
    "Original cell blank · continued from A5 (row 5)",
  );
});

test("contributor instructions, clarification explanations and correction stay in one chat", async ({
  page,
}, info) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const checkpoints: Record<string, unknown> = {};
  const exchanges: unknown[] = [];
  const captures: Promise<void>[] = [];
  page.on("response", (response) => {
    if (
      response.url().endsWith("/query") &&
      response.request().method() === "POST"
    )
      captures.push(
        (async () => {
          exchanges.push({
            request: response.request().postDataJSON(),
            http_status: response.status(),
            response: await response.json(),
          });
        })(),
      );
  });
  try {
    await page.goto("/");
    await expect(page.getByLabel("Upload document")).toBeEnabled();
    await upload(
      page,
      "sample_sales_extended.xlsx",
      `contributors-${info.project.name}.xlsx`,
    );
    const answer = page.getByRole("region", { name: "Answer", exact: true });
    await ask(page, "What was the Q3 revenue in the file ?");
    const question =
      "and sum of East and West ? and Sum of North and South ? from the file and from the individual sheets, include contributed region details in the results.";
    await ask(page, question);
    await expect(
      answer.getByRole("button", { name: "Use source records →", exact: true }),
    ).toBeVisible();
    await ask(page, "what clarification you need ?");
    await expect(answer).toContainText("Question awaiting clarification:");
    await expect(answer).toContainText("Q3 Revenue");
    await expect(answer.locator(".answer-evidence")).toHaveCount(0);
    await expect(answer).not.toContainText("ORD-1002");
    const confirmedResponse = page.waitForResponse(
      (r) => r.url().endsWith("/query") && r.request().method() === "POST",
    );
    await answer
      .getByRole("button", { name: "Use source records →", exact: true })
      .click();
    checkpoints.confirmed = await captureGroups(
      page,
      (await (await confirmedResponse).json()) as Answer,
      `contributors-${info.project.name}.xlsx`,
    );
    const table = answer.getByRole("table", {
      name: "Grouped totals and available-value subtotals",
    });
    await expect(table.locator("tbody tr")).toHaveCount(9);
    const eastWest = answer.getByRole("list", {
      name: "Region contributions for Sparse Data East + West",
    });
    await expect(eastWest).toContainText("East: Missing in source");
    await expect(eastWest).toContainText("Q3 Revenue missing at B4");
    await expect(eastWest).toContainText("West: Q3 Revenue: 63,000");
    const northSouth = answer.getByRole("list", {
      name: "Region contributions for Sparse Data North + South",
    });
    await expect(northSouth).toContainText("North: Q3 Revenue: 83,000");
    await expect(northSouth).toContainText("South: No matching source records");
    await eastWest
      .getByRole("link", {
        name: "View source 7 for Sparse Data East + West East",
        exact: true,
      })
      .click();
    await expect(answer.locator("#citation-7")).toBeFocused();
    await expect(answer.locator(".answer-evidence")).toHaveAttribute("open");
    await ask(
      page,
      "Sum Q3 Revenue for East and West; Sum North and South from the file and each sheet using unicorn accounting",
    );
    await expect(answer).toContainText("'unicorn'");
    await ask(page, "what clarification you need ?");
    await expect(answer).toContainText("'unicorn'");
    await expect(answer.locator(".answer-evidence")).toHaveCount(0);
    const correctedResponse = page.waitForResponse(
      (r) => r.url().endsWith("/query") && r.request().method() === "POST",
    );
    await ask(page, question);
    checkpoints.corrected = await captureGroups(
      page,
      (await (await correctedResponse).json()) as Answer,
      `contributors-${info.project.name}.xlsx`,
    );
    await expect(
      answer.getByRole("table", {
        name: "Grouped totals and available-value subtotals",
      }),
    ).toContainText("315,000");
    await expect(answer).toContainText(
      "Retained your confirmed source-record counting choice",
    );
    await ask(
      page,
      "Sum Q3 Revenue for East and West; Sum North and South from the file and each sheet, include contributed region details in the results.",
    );
    await expect(
      answer.getByRole("button", { name: "Use source records →", exact: true }),
    ).toBeVisible();
    await expect(answer.locator(".answer-evidence")).toHaveCount(0);
    checkpoints.fresh_question = {
      requires_confirmation: true,
      evidence_count: 0,
    };
    await page.getByRole("button", { name: "New chat", exact: true }).click();
    await ask(page, "what clarification you need ?");
    await expect(answer).toContainText(
      "There is no pending clarification in this chat",
    );
    checkpoints.new_chat = {
      message: "There is no pending clarification in this chat",
      evidence_count: await answer.locator(".answer-evidence").count(),
    };
    expect(errors).toEqual([]);
  } finally {
    await Promise.all(captures);
    const currentAnswer = await page
      .getByRole("region", { name: "Answer", exact: true })
      .allInnerTexts();
    const path = info.outputPath("ui-contract.json");
    await writeFile(
      path,
      JSON.stringify(
        {
          scenario: "contributor-correction",
          project: info.project.name,
          run_id: info.config.metadata.verification_id,
          checkpoints,
          diagnostics: { exchanges, current_answer: currentAnswer },
        },
        null,
        2,
      ),
    );
    await info.attach("ui-contract", { path, contentType: "application/json" });
  }
});
