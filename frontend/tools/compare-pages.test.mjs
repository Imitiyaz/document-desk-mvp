/** Reject shared wrong answers. Author: Imitiyaz and AI Agent */
import { test } from "node:test";
import assert from "node:assert/strict";
import { comparePageContracts } from "./compare-pages.mjs";
const a = [
    ["page_1", "table_1_row_1", "BOLT-A", "10"],
    ["page_1", "table_1_row_2", "NUT-B", "6"],
  ],
  b = [
    ["page_3", "table_1_row_1", "BOLT-A", "4"],
    ["page_3", "table_1_row_2", "NUT-B", "8"],
  ];
function valid() {
  const checkpoints = {};
  for (const [key, status, scope, result, records] of [
    ["page1", "answered", ["page_1"], "16", a],
    ["confirm", "answered", ["page_1"], "16", a],
    ["page3", "answered", ["page_3"], "12", b],
    ["back", "answered", ["page_1"], "16", a],
    ["unknown", "clarification_required", ["page_99"], null, []],
    ["tableless", "clarification_required", ["page_2"], null, []],
    ["file", "answered", [], "28", [...a, ...b]],
    ["return", "answered", ["page_1"], "16", a],
    ["absent", "no_evidence", [], null, []],
    ["fresh3", "answered", ["page_3"], "12", b],
    ["fresh1", "answered", ["page_1"], "16", a],
  ])
    checkpoints[key] = {
      status,
      scope,
      result,
      records: [...records].sort(),
      operands: records.map(([s, r, , v]) => [s, r, v]).sort(),
      headline:
        "Question: Total Quantity in " + (scope.join(" and ") || "the file"),
      message: ["confirm", "file"].includes(key)
        ? "Your message: Use source records"
        : null,
      displayed: result
        ? `Total Quantity: ${result} pcs.`
        : "No matching records",
      scopeText: scope.join(","),
      coverage: "No matching source records",
    };
  return ["desktop", "mobile"].map((project) => ({
    project,
    checkpoints: structuredClone(checkpoints),
  }));
}
test("source facts and parity", () =>
  assert.deepEqual(comparePageContracts(valid()), []));
for (const kind of [
  "total",
  "scope",
  "operand",
  "question",
  "action",
  "missing",
  "coverage",
  "extra-page",
  "checkpoint",
])
  test("rejects shared wrong " + kind, () => {
    const c = valid();
    for (const x of c) {
      const p = x.checkpoints.page1;
      if (kind === "total") p.result = "28";
      if (kind === "scope") p.scope = [];
      if (kind === "operand") p.operands.pop();
      if (kind === "question") p.headline += " in page_3";
      if (kind === "action")
        x.checkpoints.confirm.headline = "Question: Use source records";
      if (kind === "missing") x.checkpoints.unknown.status = "answered";
      if (kind === "coverage")
        x.checkpoints.absent.coverage = "Requested cells present";
      if (kind === "extra-page") p.records.push(...b);
      if (kind === "checkpoint") delete x.checkpoints.fresh1;
    }
    assert.ok(comparePageContracts(c).length);
  });
test("missing mobile fails", () =>
  assert.ok(comparePageContracts(valid().slice(0, 1)).length));
