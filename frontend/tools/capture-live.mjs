/** Capture actual-model desktop demonstrations in an empty isolated workspace.
 * Only supplied synthetic files are uploaded. No ordinary data is reset/deleted.
 * Author: Imitiyaz and AI Agent
 */
import { chromium } from "@playwright/test";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL, URL } from "node:url";
import { dirname, join, resolve } from "node:path";

export function localOrigin(value) {
  const url = new URL(value);
  if (
    url.protocol !== "http:" ||
    url.hostname !== "127.0.0.1" ||
    url.username ||
    url.password ||
    url.pathname !== "/" ||
    url.search ||
    url.hash
  )
    throw new Error(
      "Use a loopback application origin, such as http://127.0.0.1:5173/",
    );
  return url.origin;
}
export function requireEmptyCatalog(catalog) {
  if (!Array.isArray(catalog) || catalog.length)
    throw new Error(
      "Use an empty isolated review workspace; existing documents were not changed",
    );
}
export function verifyNarrative(body) {
  if (
    body.status !== "answered" ||
    body.execution_path !== "source_grounded_summary" ||
    !body.model ||
    !body.answer.includes("not approved") ||
    !body.answer.includes("2026-11-03")
  )
    throw new Error(
      "Actual-model narrative check did not complete; fallback/excerpts are not model-synthesis success",
    );
}

/** Persist the request/response before checking it, including unsuccessful runs.
 * A rejected answer remains evidence. A screenshot failure must not erase the
 * server response or replace the original verification error.
 */
export async function recordQuery({
  question,
  scenario,
  manifest,
  save,
  perform,
  verify,
  captureUi,
}) {
  const entry = {
    scenario,
    question,
    status: "running",
    validation_status: "not_run",
  };
  manifest.captures.push(entry);
  save();
  let stage = "request";
  let captureAttempted = false;
  try {
    const response = await perform();
    entry.http_status = response.status();
    stage = "response_body";
    save();
    entry.raw_response = await response.text();
    // Save raw bytes-as-text before JSON parsing: error pages need not be JSON.
    save();
    stage = "response_json";
    try {
      entry.api_response = JSON.parse(entry.raw_response);
    } catch (error) {
      entry.response_parse_error = String(error);
      if (entry.http_status === 200) throw error;
    }
    save();
    stage = "http_status";
    if (entry.http_status !== 200)
      throw new Error(`Query failed: HTTP ${entry.http_status}`);
    stage = "answer_validation";
    verify(entry.api_response);
    entry.validation_status = "passed";
    save();
    stage = "ui_capture";
    captureAttempted = true;
    Object.assign(entry, await captureUi(entry.api_response, false));
    entry.status = "passed";
  } catch (error) {
    entry.status = "failed";
    entry.failed_stage = stage;
    entry.error = String(error);
    if (stage === "answer_validation") entry.validation_status = "failed";
    save();
    if (!captureAttempted) {
      try {
        Object.assign(entry, await captureUi(entry.api_response, true));
      } catch (captureError) {
        entry.capture_error = String(captureError);
      }
    }
    // Preserve the primary failure even if the DOM/browser cannot be captured.
    throw error;
  } finally {
    save();
  }
  return entry;
}

export async function main(args = process.argv.slice(2)) {
  const option = (key, fallback) => {
    const at = args.indexOf(key);
    return at < 0 ? fallback : args[at + 1];
  };
  const origin = localOrigin(option("--url", "http://127.0.0.1:5173/"));
  const width = Number(option("--width", "1440"));
  if (![1280, 1440, 1920].includes(width))
    throw new Error("Choose a documented desktop width: 1280, 1440 or 1920");
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
  const output = resolve(
    option(
      "--output",
      join(
        root,
        "reports/screenshots-live",
        new Date().toISOString().replaceAll(/[:.]/g, "-"),
      ),
    ),
  );
  mkdirSync(dirname(output), { recursive: true });
  mkdirSync(output, { recursive: false });
  const json = async (path, options = {}) => {
    const response = await globalThis.fetch(origin + "/api" + path, options);
    if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
    return response.json();
  };
  const manifest = {
    application_version: "0.3.8",
    capture_schema_version: 2,
    operator_mode: "actual_model_required_for_narrative",
    origin,
    viewport: { width, height: 1000 },
    status: "running",
    captures: [],
  };
  const save = () =>
    writeFileSync(
      join(output, "manifest.json"),
      JSON.stringify(manifest, null, 2),
    );
  save();
  let browser;
  try {
    const catalog = await json("/documents");
    requireEmptyCatalog(catalog);
    const schema = await json("/openapi.json");
    if (schema.info?.version !== "0.3.8")
      throw new Error("Expected application 0.3.8");
    browser = await chromium.launch({
      executablePath: process.env.BROWSER_EXECUTABLE || undefined,
    });
    const page = await browser.newPage({ viewport: { width, height: 1000 } });
    await page.goto(origin);
    async function upload(relative, name) {
      await page
        .locator(".library-caption")
        .filter({ hasText: /^\d+ indexed documents?$/ })
        .waitFor();
      await page.getByLabel("Upload document").setInputFiles({
        name,
        mimeType: name.endsWith("pdf")
          ? "application/pdf"
          : "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        buffer: readFileSync(join(root, relative)),
      });
      await page
        .getByRole("status")
        .filter({ hasText: `${name} indexed` })
        .waitFor({ timeout: 240000 });
    }
    async function ask(question, scenario, verify) {
      await recordQuery({
        scenario,
        question,
        manifest,
        save,
        verify,
        perform: async () => {
          await page.getByLabel("Your question").fill(question);
          const [response] = await Promise.all([
            page.waitForResponse(
              (r) =>
                r.url().endsWith("/query") && r.request().method() === "POST",
              { timeout: 240000 },
            ),
            page.getByRole("button", { name: "Find answer" }).click(),
          ]);
          return response;
        },
        captureUi: async (body, failed) => {
          await page
            .getByRole("button", { name: "Stop waiting" })
            .waitFor({ state: "detached", timeout: failed ? 10000 : 30000 });
          if (!failed)
            await page
              .locator(".answered-question")
              .filter({ hasText: body.resolved_question || question })
              .waitFor();
          const file = `${width}-${scenario}${failed ? "-failed" : ""}.png`;
          await page.screenshot({
            path: join(output, file),
            fullPage: true,
            animations: "disabled",
          });
          const cards = page.locator(".answer-card");
          return {
            file,
            displayed_answer: (await cards.count())
              ? await cards.last().innerText()
              : "",
          };
        },
      });
    }
    await upload("backend/tests/fixtures/sample_sales.xlsx", "demo-sales.xlsx");
    await ask(
      "What was the Q3 revenue for North in the Q3 Sales sheet?",
      "lookup",
      (b) => {
        if (
          b.records?.length !== 1 ||
          b.records[0].values["Q3 Revenue"] !== "45000" ||
          b.records[0].cell_references["Q3 Revenue"] !== "B2"
        )
          throw new Error("Lookup value/source mismatch");
      },
    );
    await upload(
      "backend/tests/fixtures/acceptance/hours.xlsx",
      "demo-hours.xlsx",
    );
    await ask("What is the sum of Hours?", "subtotal", (b) => {
      if (b.calculation?.result.Hours !== "15.75" || !b.calculation.partial)
        throw new Error("Missing-value subtotal mismatch");
    });
    await upload(
      "backend/tests/fixtures/acceptance/operations.pdf",
      "demo-operations.pdf",
    );
    await ask(
      "Is Orchid production launch approved and when is the next review?",
      "actual-model-narrative",
      verifyNarrative,
    );
    await ask(
      "Is Rose production launch approved and when is the next review?",
      "unknown-subject",
      (b) => {
        if (
          b.status !== "no_evidence" ||
          b.citations.length ||
          /Orchid|2026-11-03/.test(b.answer)
        )
          throw new Error("Wrong-subject answer");
      },
    );
    manifest.status = "passed";
  } catch (error) {
    manifest.status = "failed";
    manifest.error = String(error);
    process.exitCode = 1;
  } finally {
    await browser?.close().catch(() => undefined);
    save();
    console.log("CAPTURE REPORT: " + join(output, "manifest.json"));
  }
}
if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
)
  await main();
