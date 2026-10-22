/** Independent facts plus desktop/mobile equality for the approved intent fix.
 * Author: Imitiyaz and AI Agent
 */
import { readFile, writeFile } from "node:fs/promises";
import { isDeepStrictEqual } from "node:util";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
const a = [
  ["Work log", 2, "7.5"],
  ["Work log", 3, "8.25"],
  ["Work log", 5, "0"],
];
const absent = ["no_evidence", [["result", null]], []];
const facts = {
  products: {
    absent,
    known: [
      "answered",
      [["result", null]],
      [
        ["page_1", "table_1_row_1", "10"],
        ["page_3", "table_1_row_1", "4"],
      ],
    ],
    grouped: [
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
    ],
    after_confirm: absent,
    fresh: absent,
    mixed: ["clarification_required", [["result", null]], []],
  },
  hours: {
    alias: ["answered", [["result", "15.75"]], a],
    absent,
    missing: ["incomplete", [["result", null]], [["Work log", 4, null]]],
    returned: ["answered", [["result", "15.75"]], a],
    subtotal: [
      "incomplete",
      [["result", "15.75"]],
      [...a.slice(0, 2), ["Work log", 4, null], a[2]],
    ],
    canonical: ["answered", [["result", "15.75"]], a],
    qualifier: ["clarification_required", [["result", null]], []],
  },
};
export function compareIntentContracts(contracts) {
  const findings = [];
  for (const scenario of ["products", "hours"]) {
    const pair = contracts.filter((c) => c.scenario === scenario);
    if (
      !isDeepStrictEqual(pair.map((c) => c.project).sort(), [
        "desktop",
        "mobile",
      ])
    )
      findings.push(
        `${scenario}: exactly one desktop and mobile contract required`,
      );
    for (const c of pair) {
      if (
        !isDeepStrictEqual(
          Object.keys(c.checkpoints ?? {}).sort(),
          Object.keys(facts[scenario]).sort(),
        )
      )
        findings.push(`${scenario}/${c.project}: wrong checkpoint coverage`);
      for (const [key, [status, results, records]] of Object.entries(
        facts[scenario],
      )) {
        const got = c.checkpoints?.[key];
        if (
          !got ||
          got.status !== status ||
          !isDeepStrictEqual(got.results, results) ||
          !isDeepStrictEqual(got.records, records)
        )
          findings.push(
            `${scenario}/${c.project}/${key}: answer differs from independent source facts`,
          );
        if (!got?.visible?.trim())
          findings.push(
            `${scenario}/${c.project}/${key}: visible answer missing`,
          );
        if (
          got &&
          status === "no_evidence" &&
          (!got.visible.includes("No matching") ||
            !got.visible.includes(scenario === "products" ? "Apple" : "Zenzee"))
        )
          findings.push(`${scenario}/${key}: absent name not explained`);
        if (
          got &&
          scenario === "hours" &&
          ["alias", "returned", "canonical", "subtotal"].includes(key) &&
          !got.visible.includes("15.75 hours")
        )
          findings.push(`${scenario}/${key}: visible result is wrong`);
        if (got && key === "subtotal" && !got.visible.includes("subtotal"))
          findings.push("Missing-cell subtotal warning absent");
        if (
          got &&
          scenario === "hours" &&
          key === "missing" &&
          !got.visible.includes("Missing in source")
        )
          findings.push("Missing Ben value presented incorrectly");
      }
      if (
        scenario === "products" &&
        !isDeepStrictEqual(c.checkpoints?.grouped?.visibleResults, [
          ["Overall", "Quantity: 28 pcs · Total"],
          ["BOLT-A", "Quantity: 14 pcs · Total"],
          ["NUT-B", "Quantity: 14 pcs · Total"],
        ])
      )
        findings.push("Visible product-to-total association differs");
    }
    if (
      pair.length === 2 &&
      !isDeepStrictEqual(pair[0].checkpoints, pair[1].checkpoints)
    )
      findings.push(`${scenario}: desktop/mobile answers differ`);
  }
  if (contracts.length !== 4)
    findings.push("Exactly four current-run intent contracts required");
  return findings;
}
export async function compareIntentReport(path) {
  const report = JSON.parse(await readFile(path, "utf8"));
  const contracts = [],
    findings = [];
  async function walk(suite) {
    for (const spec of suite.specs ?? [])
      for (const test of spec.tests ?? []) {
        if (
          test.expectedStatus !== "passed" ||
          test.results.length !== 1 ||
          test.results[0].status !== "passed"
        )
          findings.push(
            `Failed/skipped/retried browser workflow: ${spec.title}`,
          );
        for (const result of test.results)
          for (const attachment of result.attachments ?? [])
            if (attachment.name === "intent-contract") {
              const c = JSON.parse(
                attachment.body
                  ? Buffer.from(attachment.body, "base64").toString("utf8")
                  : await readFile(attachment.path, "utf8"),
              );
              if (
                !c.run_id ||
                c.run_id !== report.config?.metadata?.verification_id
              )
                findings.push("Stale intent contract run identity");
              contracts.push(c);
            }
      }
    for (const child of suite.suites ?? []) await walk(child);
  }
  for (const suite of report.suites ?? []) await walk(suite);
  findings.push(...compareIntentContracts(contracts));
  return {
    status: findings.length ? "failed" : "passed",
    method:
      "Source facts, actual rendered results, and desktop/mobile semantic equality; not pixel or physical-device certification.",
    contracts,
    findings,
  };
}
if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  const output = process.argv[3] ?? "test-results/intent-comparison.json";
  try {
    const report = await compareIntentReport(
      process.argv[2] ?? "test-results/results.json",
    );
    await writeFile(output, JSON.stringify(report, null, 2) + "\n");
    console.log(`INTENT UI COMPARISON: ${report.status}; ${output}`);
    process.exitCode = report.findings.length ? 1 : 0;
  } catch (error) {
    await writeFile(
      output,
      JSON.stringify({ status: "failed", findings: [String(error)] }, null, 2),
    );
    console.error(String(error));
    process.exitCode = 1;
  }
}
