/**
 * Prove the UI comparator rejects coherent wrong answers and missing evidence.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { compareContracts, compareReport } from "./compare-ui.mjs";

function specimen(project) {
  const amounts = {
    "Whole file": ["315,000", "63,000", "252,000"],
    "Merged Region": ["169,000", null, "169,000"],
    "Sparse Data": ["146,000", "63,000", "83,000"],
  };
  const people = {
    "Whole file": {
      North: ["175,000", [1, 2, 5, 6]],
      South: ["77,000", [3, 4]],
      East: [null, [7]],
      West: ["63,000", [8, 9]],
    },
    "Merged Region": {
      North: ["92,000", [1, 2]],
      South: ["77,000", [3, 4]],
      East: [null, []],
      West: [null, []],
    },
    "Sparse Data": {
      North: ["83,000", [5, 6]],
      South: [null, []],
      East: [null, [7]],
      West: ["63,000", [8, 9]],
    },
  };
  const groups = [];
  for (const scope of Object.keys(amounts))
    for (const [i, label] of [
      "Overall",
      "East + West",
      "North + South",
    ].entries()) {
      const partial =
        (scope === "Whole file" && i < 2) || scope === "Sparse Data";
      const amount = amounts[scope][i];
      const names =
        label === "Overall"
          ? Object.keys(people[scope]).filter((n) => people[scope][n][1].length)
          : label.split(" + ");
      groups.push({
        scope,
        label,
        result:
          amount === null
            ? "No matching source records; no zero inferred."
            : `Q3 Revenue: ${amount} · ${partial ? "Available-value subtotal" : "Total"}`,
        contributors: names.map((entity) => {
          const [value, sources] = people[scope][entity];
          return {
            entity,
            sources,
            text: !sources.length
              ? `${entity}: No matching source records; contribution unknown, not zero.`
              : value === null
                ? `${entity}: Missing in source; contribution unknown, not zero. Q3 Revenue missing at B4.`
                : `${entity}: Q3 Revenue: ${value} · Total`,
          };
        }),
      });
    }
  const citations = [
    [1, "Merged Region", 2],
    [2, "Merged Region", 3],
    [3, "Merged Region", 4],
    [4, "Merged Region", 5],
    [5, "Sparse Data", 2],
    [6, "Sparse Data", 3],
    [7, "Sparse Data", 4],
    [8, "Sparse Data", 5],
    [9, "Sparse Data", 6],
  ];
  return {
    scenario: "contributor-correction",
    project,
    run_id: "current",
    checkpoints: {
      confirmed: { groups, citations, warnings: [] },
      corrected: {
        groups: structuredClone(groups),
        citations,
        warnings: ["Retained counting choice"],
      },
      fresh_question: { requires_confirmation: true, evidence_count: 0 },
      new_chat: {
        message: "There is no pending clarification in this chat",
        evidence_count: 0,
      },
    },
  };
}

test("reviewed results agree on desktop/mobile", () =>
  assert.deepEqual(
    compareContracts([specimen("desktop"), specimen("mobile")]),
    [],
  ));
for (const [name, change] of [
  [
    "wrong result on both screens",
    (c) => {
      c.checkpoints.confirmed.groups[0].result =
        "Q3 Revenue: 255,000 · Available-value subtotal";
    },
  ],
  [
    "missing East",
    (c) => {
      c.checkpoints.corrected.groups[7].contributors.shift();
    },
  ],
  [
    "East replaced by zero",
    (c) => {
      c.checkpoints.corrected.groups[7].contributors[0].text =
        "East: Q3 Revenue: 0 · Total";
    },
  ],
  [
    "absent South replaced by zero",
    (c) => {
      c.checkpoints.corrected.groups[8].contributors[1].text =
        "South: Q3 Revenue: 0 · Total";
    },
  ],
  [
    "wrong North amount",
    (c) => {
      c.checkpoints.corrected.groups[0].contributors[0].text =
        "North: Q3 Revenue: 45,000 · Total";
    },
  ],
  [
    "lost citation",
    (c) => {
      c.checkpoints.corrected.groups[0].contributors[0].sources.pop();
    },
  ],
  [
    "missing checkpoint",
    (c) => {
      delete c.checkpoints.corrected;
    },
  ],
  [
    "new chat leaks evidence",
    (c) => {
      c.checkpoints.new_chat.evidence_count = 1;
    },
  ],
  [
    "fresh question silently inherits confirmation",
    (c) => {
      c.checkpoints.fresh_question.requires_confirmation = false;
    },
  ],
])
  test(name, () => {
    const a = specimen("desktop"),
      b = specimen("mobile");
    change(a);
    change(b);
    assert.ok(compareContracts([a, b]).length);
  });
test("one differing warning fails parity", () => {
  const a = specimen("desktop"),
    b = specimen("mobile");
  b.checkpoints.corrected.warnings = [];
  assert.ok(compareContracts([a, b]).length);
});
test("missing mobile is incomplete", () =>
  assert.ok(compareContracts([specimen("desktop")]).length));
test("report rejects skipped workflows and stale attachments", async () => {
  const dir = await mkdtemp(join(tmpdir(), "rag-ui-checker-"));
  try {
    const contracts = [specimen("desktop"), specimen("mobile")];
    const report = {
      config: { metadata: { verification_id: "current" } },
      suites: [
        {
          specs: [
            {
              title: "flow",
              tests: contracts.map((c) => ({
                projectName: c.project,
                expectedStatus: "passed",
                results: [
                  {
                    status: "passed",
                    attachments: [
                      {
                        name: "ui-contract",
                        body: Buffer.from(JSON.stringify(c)).toString("base64"),
                      },
                    ],
                  },
                ],
              })),
            },
          ],
        },
      ],
    };
    const path = join(dir, "results.json");
    await writeFile(path, JSON.stringify(report));
    assert.equal((await compareReport(path)).status, "passed");
    report.suites[0].specs[0].tests[1].results[0].status = "skipped";
    await writeFile(path, JSON.stringify(report));
    assert.equal((await compareReport(path)).status, "failed");
    report.config.metadata.verification_id = "new-run";
    await writeFile(path, JSON.stringify(report));
    assert.ok(
      (await compareReport(path)).findings.some((f) => f.includes("Stale")),
    );
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
});
