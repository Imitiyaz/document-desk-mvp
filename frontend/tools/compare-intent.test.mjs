/** Checker mutations must reject two identical but incorrect viewports.
 * Author: Imitiyaz and AI Agent
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { compareIntentContracts } from "./compare-intent.mjs";
const a = [
  ["Work log", 2, "7.5"],
  ["Work log", 3, "8.25"],
  ["Work log", 5, "0"],
];
const point = (
  status = "no_evidence",
  results = [["result", null]],
  records = [],
  visible = "No matching Name records for Zenzee; No matching Product records for Apple",
) => ({ status, results, records, visible, visibleResults: [] });
function valid() {
  const products = {
    absent: point(),
    known: point(
      "answered",
      [["result", null]],
      [
        ["page_1", "table_1_row_1", "10"],
        ["page_3", "table_1_row_1", "4"],
      ],
    ),
    grouped: {
      ...point(
        "answered",
        [
          ["Overall", "28"],
          ["BOLT-A", "14"],
          ["NUT-B", "14"],
        ],
        [
          ["page_1", "table_1_row_1", "10"],
          ["page_1", "table_1_row_2", "6"],
          ["page_3", "table_1_row_1", "4"],
          ["page_3", "table_1_row_2", "8"],
        ],
      ),
      visibleResults: [
        ["Overall", "Quantity: 28 pcs · Total"],
        ["BOLT-A", "Quantity: 14 pcs · Total"],
        ["NUT-B", "Quantity: 14 pcs · Total"],
      ],
    },
    after_confirm: point(),
    fresh: point(),
    mixed: point("clarification_required"),
  };
  const hours = {
    alias: point("answered", [["result", "15.75"]], a, "15.75 hours"),
    absent: point(),
    missing: point(
      "incomplete",
      [["result", null]],
      [["Work log", 4, null]],
      "Ben — Hours: Missing in source",
    ),
    returned: point("answered", [["result", "15.75"]], a, "15.75 hours"),
    subtotal: point(
      "incomplete",
      [["result", "15.75"]],
      [...a.slice(0, 2), ["Work log", 4, null], a[2]],
      "Available-value subtotal: 15.75 hours",
    ),
    canonical: point("answered", [["result", "15.75"]], a, "15.75 hours"),
    qualifier: point("clarification_required"),
  };
  return ["products", "hours"].flatMap((scenario) =>
    ["desktop", "mobile"].map((project) => ({
      scenario,
      project,
      checkpoints: structuredClone(scenario === "products" ? products : hours),
    })),
  );
}
test("reviewed source facts agree across viewports", () =>
  assert.deepEqual(compareIntentContracts(valid()), []));
for (const kind of [
  "sum",
  "record",
  "zero",
  "missing",
  "warning",
  "visible",
  "absent",
  "checkpoint",
  "duplicate",
])
  test(`rejects ${kind} even in identical wrong viewports`, () => {
    const list = valid();
    for (const c of list) {
      if (kind === "sum" && c.scenario === "products")
        c.checkpoints.grouped.results[0][1] = "29";
      if (kind === "record" && c.scenario === "products")
        c.checkpoints.grouped.records.pop();
      if (kind === "zero" && c.scenario === "hours")
        c.checkpoints.alias.records.pop();
      if (kind === "missing" && c.scenario === "hours")
        c.checkpoints.missing.records[0][2] = "0";
      if (kind === "warning" && c.scenario === "hours")
        c.checkpoints.subtotal.visible = "15.75 hours";
      if (kind === "visible" && c.scenario === "products")
        c.checkpoints.grouped.visibleResults[1][1] = "Quantity: 28 pcs · Total";
      if (kind === "absent") c.checkpoints.absent.status = "answered";
      if (kind === "checkpoint") delete c.checkpoints.absent;
    }
    if (kind === "duplicate") list.push(structuredClone(list[0]));
    assert.ok(compareIntentContracts(list).length);
  });
test("missing mobile output fails", () =>
  assert.ok(
    compareIntentContracts(valid().filter((c) => c.project === "desktop"))
      .length,
  ));
