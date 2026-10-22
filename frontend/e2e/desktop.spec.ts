/** Real desktop DOM/API/screenshot checks. Synthetic documents; controlled models.
 * Author: Imitiyaz and AI Agent
 */
import { test, expect, type Page } from "@playwright/test";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { Answer } from "../src/api";
import {
  documentLibraryReadyText,
  confirmationDialogRole,
  keepDataButtonName,
} from "./control-names";

async function upload(page: Page, fixture: string, name: string) {
  await expect(page.locator(".library-caption")).toHaveText(
    documentLibraryReadyText,
  );
  const old = page.getByRole("button", { name: `Remove ${name}`, exact: true });
  if (await old.count()) {
    await old.click();
    await page
      .getByRole("button", { name: "Confirm removal", exact: true })
      .click();
    await expect(old).toHaveCount(0);
  }
  await page.getByLabel("Upload document").setInputFiles({
    name,
    mimeType: name.endsWith("pdf")
      ? "application/pdf"
      : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    buffer: readFileSync(fixture),
  });
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
  await expect(page.locator(".answer-card .answered-question")).toContainText(
    body.resolved_question || question,
  );
  await expect(page.getByRole("button", { name: "Stop waiting" })).toHaveCount(
    0,
  );
  return body;
}
for (const width of [1280, 1440, 1920]) {
  test(`desktop ${width}: lookup, follow-up, subtotal, subject abstention and keyboard evidence`, async ({
    page,
  }, info) => {
    test.skip(
      info.project.name !== "desktop",
      "Desktop capture suite; historical mobile workflows are separate",
    );
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    const output = join("test-results", "desktop");
    mkdirSync(output, { recursive: true });
    const captures: {
      scenario: string;
      path: string;
      api_response: Answer;
      displayed_answer: string;
    }[] = [];
    function saveCaptures(status: "partial" | "passed") {
      writeFileSync(
        join(output, `${width}-manifest.json`),
        JSON.stringify(
          {
            application_version: "0.3.8",
            mode: "real_browser_controlled_embedding_vector_and_model",
            verification_status: status,
            viewport: { width, height: 1000 },
            browser_project: info.project.name,
            captures,
          },
          null,
          2,
        ),
      );
    }
    async function capture(scenario: string) {
      const filename = `${width}-${scenario}.png`;
      await page.screenshot({
        path: join(output, filename),
        fullPage: true,
        animations: "disabled",
      });
      captures.push({
        scenario,
        path: filename,
        api_response: body,
        displayed_answer: await page
          .getByRole("region", { name: "Answer", exact: true })
          .innerText(),
      });
      // Keep captured responses even if a later interaction fails. Partial
      // evidence cannot be mistaken for a passed width workflow.
      saveCaptures("partial");
    }
    await upload(
      page,
      "../backend/tests/fixtures/sample_sales.xlsx",
      `desktop-${width}-sales.xlsx`,
    );
    let body = await ask(
      page,
      "What was the Q3 revenue for North in the Q3 Sales sheet?",
    );
    expect(body.records.map((r) => r.values["Q3 Revenue"])).toEqual(["45000"]);
    expect(body.records[0].cell_references["Q3 Revenue"]).toBe("B2");
    await expect(page.locator(".answer-primary")).toContainText("45,000");
    await expect(page.locator(".answer-evidence")).not.toHaveAttribute(
      "open",
      "",
    );
    const link = page.getByRole("link", { name: "View source 1", exact: true });
    await link.focus();
    await link.press("Enter");
    await expect(page.locator(".answer-evidence")).toHaveAttribute("open", "");
    await expect(page.locator("#citation-1")).toBeFocused();
    await capture("lookup-evidence");
    body = await ask(page, "And South?");
    expect(body.records.map((r) => r.values["Q3 Revenue"])).toEqual(["38000"]);
    expect(body.records[0].cell_references["Q3 Revenue"]).toBe("B3");
    await upload(
      page,
      "../backend/tests/fixtures/acceptance/hours.xlsx",
      `desktop-${width}-hours.xlsx`,
    );
    body = await ask(page, "What is the sum of Hours?");
    expect(body.calculation?.result).toEqual({ Hours: "15.75" });
    expect(body.calculation?.partial).toBe(true);
    expect(body.calculation?.operands?.map((o) => o.values["Hours"])).toEqual([
      "7.5",
      "8.25",
      "0",
    ]);
    expect(body.calculation?.excluded_cells).toHaveLength(1);
    await expect(page.locator(".answer-primary")).toContainText(/subtotal/i);
    await expect(page.locator(".answer-primary")).toContainText("15.75");
    await capture("subtotal-warning");
    await upload(
      page,
      "../backend/tests/fixtures/acceptance/operations.pdf",
      `desktop-${width}-operations.pdf`,
    );
    body = await ask(
      page,
      "Is Rose production launch approved and when is the next review?",
    );
    expect(body.status).toBe("no_evidence");
    expect(body.citations).toEqual([]);
    expect(body.answer).not.toMatch(/Orchid|2026-11-03/);
    await expect(page.locator(".answer-primary")).toContainText("Rose");
    await capture("unknown-subject");
    const dimensions = await page.evaluate(() => ({
      viewport: innerWidth,
      page: document.documentElement.scrollWidth,
      workspace: document
        .querySelector(".workspace-grid")!
        .getBoundingClientRect().width,
    }));
    expect(dimensions.page).toBeLessThanOrEqual(dimensions.viewport + 1);
    expect(dimensions.workspace).toBeGreaterThan(dimensions.viewport * 0.9);
    const documentOptions = page
      .getByLabel("Document", { exact: true })
      .locator("option");
    const documentsBefore = await documentOptions.allTextContents();
    const answer = page.getByRole("region", { name: "Answer", exact: true });
    const answerBefore = await answer.innerText();
    const reset = page.getByRole("button", {
      name: "Reset workspace",
      exact: true,
    });
    const deletions: string[] = [];
    const watchDeletion = (request: { method(): string; url(): string }) => {
      if (request.method() === "DELETE") deletions.push(request.url());
    };
    page.on("request", watchDeletion);
    await reset.click();
    const confirmation = page.getByRole(confirmationDialogRole);
    await expect(confirmation).toBeVisible();
    const keep = confirmation.getByRole("button", {
      name: keepDataButtonName,
      exact: true,
    });
    await expect(keep).toBeFocused();
    await keep.click();
    await expect(confirmation).toHaveCount(0);
    await expect(reset).toBeFocused();
    expect(await documentOptions.allTextContents()).toEqual(documentsBefore);
    expect(await answer.innerText()).toBe(answerBefore);
    expect(deletions).toEqual([]);
    page.off("request", watchDeletion);
    saveCaptures("passed");
  });
}
