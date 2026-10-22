/** Scope populations, original messages and actual confirmation controls.
 * Author: Imitiyaz and AI Agent
 */
import { test, expect } from "@playwright/test";
import type { Answer } from "../src/api";
import { sourceRecordsButtonName, answerTextSelector, documentLibraryReadyText } from "./control-names";

test("explicit page population survives confirmation, source change and new chat", async ({
  page,
}, info) => {
  const points: Record<string, unknown> = {};
  await page.goto("/");
  await expect(page.locator(".library-caption")).toHaveText(documentLibraryReadyText);
  await expect(page.getByLabel("Upload document")).toBeEnabled();
  const old = page.getByRole("button", {
    name: "Remove operations.pdf",
    exact: true,
  });
  if (await old.count()) {
    await old.click();
    await page
      .getByRole("button", { name: "Confirm removal", exact: true })
      .click();
    await expect(old).toHaveCount(0);
  }
  await page
    .getByLabel("Upload document")
    .setInputFiles("../backend/tests/fixtures/acceptance/operations.pdf");
  await expect(page.getByRole("status")).toContainText(
    "operations.pdf indexed",
  );
  const card = page.getByRole("region", { name: "Answer", exact: true });
  async function ask(q: string, click = false): Promise<Answer> {
    const pending = page.waitForResponse(
      (r) => r.url().endsWith("/query") && r.request().method() === "POST",
    );
    if (click)
      await card
        .getByRole("button", { name: sourceRecordsButtonName, exact: true })
        .click();
    else {
      await page.getByLabel("Your question").fill(q);
      await page.getByRole("button", { name: "Find answer" }).click();
    }
    const reply = await pending;
    expect(reply.status()).toBe(200);
    const b: Answer = await reply.json();
    await expect(
      page.getByRole("button", { name: "Stop waiting" }),
    ).toHaveCount(0);
    await expect(card.locator(".answered-question")).toHaveText(
      `Question: ${b.resolved_question || q}`,
    );
    expect(reply.request().postDataJSON().group_field).toBeUndefined();
    return b;
  }
  async function save(key: string, b: Answer) {
    points[key] = {
      status: b.status,
      scope: b.coverage.resolved_scopes,
      result: b.calculation?.result.Quantity ?? null,
      records: b.records
        .map((r) => [
          r.sheet_or_page,
          r.row_or_location,
          r.values.Product,
          r.values.Quantity,
        ])
        .sort(),
      operands: (b.calculation?.operands ?? [])
        .map((o) => [
          o.source?.sheet_or_page,
          o.source?.row_or_location,
          o.values.Quantity,
        ])
        .sort(),
      headline: await card.locator(".answered-question").innerText(),
      message: (await card.locator(".user-message").count())
        ? await card.locator(".user-message").innerText()
        : null,
      displayed: await card.locator(answerTextSelector).innerText(),
      scopeText: await card.locator(".resolved-scope").innerText(),
      coverage: (await card.locator(".coverage").count())
        ? await card.locator(".coverage").innerText()
        : null,
    };
  }
  async function scoped(b: Answer, total: string, scope: string) {
    expect(b.status).toBe("answered");
    expect(b.calculation?.result.Quantity).toBe(total);
    expect(b.coverage.resolved_scopes).toEqual([scope]);
    expect(b.records).toHaveLength(2);
    expect(b.calculation?.operands).toHaveLength(2);
    expect([...new Set(b.records.map((r) => r.sheet_or_page))]).toEqual([
      scope,
    ]);
    await expect(card.locator(".readable-answer")).toContainText(
      `${total} pcs`,
    );
    await expect(card.locator(".answered-question")).toContainText(scope);
    await expect(
      card.getByRole("button", { name: sourceRecordsButtonName, exact: true }),
    ).toHaveCount(0);
  }
  let b = await ask(
    "What is the total quantity of NUT-B and BOLT-A in page 1?",
  );
  await scoped(b, "16", "page_1");
  await expect(card.locator(".answer-evidence")).not.toHaveAttribute("open");
  await card
    .getByRole("link", { name: "View source 1", exact: true })
    .first()
    .focus();
  await page.keyboard.press("Enter");
  await expect(card.locator("#citation-1")).toBeFocused();
  const rows = card.locator(".answer-evidence tbody tr");
  await expect(rows).toHaveCount(2);
  for (let i = 0; i < 2; i++) {
    await expect(rows.nth(i)).toContainText("page_1");
    await expect(rows.nth(i)).not.toContainText("page_3");
  }
  await save("page1", b);
  b = await ask("Use source records");
  await scoped(b, "16", "page_1");
  await expect(card.locator(".user-message")).toHaveText(
    "Your message: Use source records",
  );
  await save("confirm", b);
  b = await ask("page_3");
  await scoped(b, "12", "page_3");
  await expect(card.locator(".answered-question")).not.toContainText("page_1");
  await save("page3", b);
  b = await ask("And page 1?");
  await scoped(b, "16", "page_1");
  await save("back", b);
  b = await ask("page 99");
  expect(b.status).toBe("clarification_required");
  expect(b.records).toEqual([]);
  expect(b.calculation).toBeNull();
  await expect(card.locator(answerTextSelector)).toContainText("page_99");
  await save("unknown", b);
  b = await ask("Total Quantity in page 2?");
  expect(b.status).toBe("clarification_required");
  expect(b.records).toEqual([]);
  await expect(card.locator(answerTextSelector)).toContainText("no extracted table records");
  await save("tableless", b);
  b = await ask("Total Quantity for NUT-B and BOLT-A in the file?");
  expect(b.status).toBe("clarification_required");
  b = await ask("Use source records", true);
  expect(b.calculation?.result.Quantity).toBe("28");
  await expect(card.locator(".answered-question")).toHaveText(
    "Question: Total Quantity for NUT-B and BOLT-A in the file?",
  );
  await expect(card.locator(".user-message")).toHaveText(
    "Your message: Use source records",
  );
  await save("file", b);
  b = await ask("page_1");
  await scoped(b, "16", "page_1");
  await save("return", b);
  b = await ask("Quantity for Apple in the file?");
  expect(b.status).toBe("no_evidence");
  await expect(card.locator(".coverage")).toContainText(
    "No matching source records",
  );
  await expect(card.locator(".coverage")).not.toContainText(
    "Requested cells present",
  );
  await save("absent", b);
  await page.getByRole("button", { name: "New chat", exact: true }).click();
  b = await ask("Total Quantity for NUT-B and BOLT-A on page-3?");
  await scoped(b, "12", "page_3");
  await save("fresh3", b);
  b = await ask("Total Quantity for NUT-B and BOLT-A on page_1?");
  await scoped(b, "16", "page_1");
  await save("fresh1", b);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await info.attach("page-scope-contract", {
    body: JSON.stringify(
      {
        project: info.project.name,
        run_id: info.config.metadata.verification_id,
        checkpoints: points,
      },
      null,
      2,
    ),
    contentType: "application/json",
  });
});
