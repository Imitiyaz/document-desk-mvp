/** Privacy and truthfulness boundaries for live screenshot capture.
 * Author: Imitiyaz and AI Agent
 */
import test from "node:test";
import assert from "node:assert/strict";
import {
  main,
  localOrigin,
  requireEmptyCatalog,
  verifyNarrative,
  recordQuery,
} from "./capture-live.mjs";
test("capture rejects remote hosts, credentials and misleading loopback prefixes", () => {
  for (const value of [
    "https://example.com",
    "http://127.0.0.1:80@example.com/",
    "http://127.0.0.1:5173/?token=x",
    "http://localhost:5173/",
  ])
    assert.throws(() => localOrigin(value));
  assert.equal(localOrigin("http://127.0.0.1:5173/"), "http://127.0.0.1:5173");
});

function response(status, text) {
  const actual = new globalThis.Response(text, { status });
  return { status: () => actual.status, text: () => actual.text() };
}

function recording() {
  const manifest = { captures: [] };
  const saved = [];
  return {
    manifest,
    saved,
    options: {
      question: "Is Orchid production launch approved?",
      scenario: "actual-model-narrative",
      manifest,
      save: () => saved.push(JSON.parse(JSON.stringify(manifest))),
      verify: verifyNarrative,
      captureUi: async () => ({
        file: "failed.png",
        displayed_answer: "Excerpt",
      }),
    },
  };
}

test("rejected fallback is saved before validation, including the failed UI capture", async () => {
  const { options, saved, manifest } = recording();
  const fallback = {
    status: "evidence_only",
    execution_path: "source_excerpts",
    model: null,
    answer: "Orchid is not approved. Next review: 2026-11-03.",
  };
  await assert.rejects(
    recordQuery({
      ...options,
      perform: async () => response(200, JSON.stringify(fallback)),
      verify: (body) => {
        assert.deepEqual(saved.at(-1).captures[0].api_response, fallback);
        verifyNarrative(body);
      },
    }),
    /fallback\/excerpts/,
  );
  const entry = manifest.captures[0];
  assert.equal(entry.http_status, 200);
  assert.deepEqual(entry.api_response, fallback);
  assert.equal(entry.raw_response, JSON.stringify(fallback));
  assert.equal(entry.status, "failed");
  assert.equal(entry.validation_status, "failed");
  assert.equal(entry.failed_stage, "answer_validation");
  assert.equal(entry.file, "failed.png");
  assert.equal(saved.at(-1).captures[0].status, "failed");
});

test("HTTP errors retain JSON and HTML response bodies without claiming validation", async () => {
  for (const text of [
    '{"code":"llm_unavailable"}',
    "<html>Bad gateway</html>",
  ]) {
    const { options, manifest } = recording();
    await assert.rejects(
      recordQuery({
        ...options,
        perform: async () => response(503, text),
        verify: () =>
          assert.fail("A failed HTTP request must not be validated"),
      }),
      /HTTP 503/,
    );
    assert.equal(manifest.captures[0].raw_response, text);
    assert.equal(manifest.captures[0].http_status, 503);
    assert.equal(manifest.captures[0].validation_status, "not_run");
  }
});

test("invalid successful JSON is preserved even if screenshot capture also fails", async () => {
  const { options, manifest } = recording();
  await assert.rejects(
    recordQuery({
      ...options,
      perform: async () => response(200, "not JSON"),
      captureUi: async () => {
        throw new Error("Browser closed");
      },
    }),
    SyntaxError,
  );
  const entry = manifest.captures[0];
  assert.equal(entry.raw_response, "not JSON");
  assert.equal(entry.failed_stage, "response_json");
  assert.match(entry.capture_error, /Browser closed/);
  assert.match(entry.error, /SyntaxError/);
});

test("transport errors leave a request record and preserve the primary error", async () => {
  const { options, manifest } = recording();
  await assert.rejects(
    recordQuery({
      ...options,
      perform: async () => {
        throw new Error("Response wait timed out");
      },
      captureUi: async () => {
        throw new Error("No DOM");
      },
    }),
    /Response wait timed out/,
  );
  assert.equal(manifest.captures[0].question, options.question);
  assert.equal(manifest.captures[0].failed_stage, "request");
  assert.match(manifest.captures[0].capture_error, /No DOM/);
});

test("a UI failure retains validated server data without calling the capture passed", async () => {
  const { options, manifest } = recording();
  const body = { status: "answered", answer: "45,000" };
  await assert.rejects(
    recordQuery({
      ...options,
      perform: async () => response(200, JSON.stringify(body)),
      verify: () => {},
      captureUi: async () => {
        throw new Error("Screenshot write failed");
      },
    }),
    /Screenshot write failed/,
  );
  assert.equal(manifest.captures[0].validation_status, "passed");
  assert.equal(manifest.captures[0].status, "failed");
  assert.deepEqual(manifest.captures[0].api_response, body);
});

test("successful queries retain previous captures and save complete displayed evidence", async () => {
  const { options, manifest, saved } = recording();
  manifest.captures.push({ scenario: "lookup", status: "passed" });
  const body = {
    status: "answered",
    execution_path: "source_grounded_summary",
    model: "operator-selected-model",
    answer: "Orchid is not approved. Next review: 2026-11-03.",
  };
  const entry = await recordQuery({
    ...options,
    perform: async () => response(200, JSON.stringify(body)),
    captureUi: async () => ({
      file: "narrative.png",
      displayed_answer: body.answer,
    }),
  });
  assert.equal(entry.status, "passed");
  assert.equal(entry.validation_status, "passed");
  assert.equal(entry.displayed_answer, body.answer);
  assert.equal(manifest.captures.length, 2);
  assert.equal(saved.at(-1).captures[0].scenario, "lookup");
  assert.equal(saved.at(-1).captures[1].file, "narrative.png");
});
test("capture refuses existing data before any browser interaction", () => {
  assert.throws(() => requireEmptyCatalog([{ source_file: "business.xlsx" }]));
  assert.throws(() => requireEmptyCatalog({}));
  requireEmptyCatalog([]);
});
test("excerpt fallback is not counted as actual-model narrative success", () => {
  assert.throws(() =>
    verifyNarrative({
      status: "evidence_only",
      execution_path: "source_excerpts",
      model: null,
      answer: "not approved 2026-11-03",
    }),
  );
});
test("verified actual-model narrative must retain both polarity and date", () => {
  const body = {
    status: "answered",
    execution_path: "source_grounded_summary",
    model: "operator-selected-model",
    answer: "Orchid is not approved. Next review: 2026-11-03.",
  };
  verifyNarrative(body);
  assert.throws(() =>
    verifyNarrative({
      ...body,
      answer: "Orchid is approved. Next review: 2026-11-03.",
    }),
  );
});

// This exercises report creation before browser launch, including nested output dirs.
test("failed existing-data preflight still produces a fresh failure manifest", async () => {
  const { mkdtempSync, readFileSync, rmSync } = await import("node:fs");
  const { tmpdir } = await import("node:os");
  const { join } = await import("node:path");
  const temporary = mkdtempSync(join(tmpdir(), "rag-capture-check-"));
  const priorFetch = globalThis.fetch;
  const priorExit = process.exitCode;
  try {
    globalThis.fetch = async () => ({
      ok: true,
      json: async () => [{ source_file: "existing.xlsx" }],
    });
    const output = join(temporary, "nested", "capture");
    await main(["--url", "http://127.0.0.1:5173/", "--output", output]);
    const manifest = JSON.parse(
      readFileSync(join(output, "manifest.json"), "utf8"),
    );
    assert.equal(manifest.status, "failed");
    assert.equal(manifest.captures.length, 0);
    assert.match(manifest.error, /existing documents were not changed/);
  } finally {
    globalThis.fetch = priorFetch;
    process.exitCode = priorExit;
    rmSync(temporary, { recursive: true, force: true });
  }
});
