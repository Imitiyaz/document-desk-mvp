/** Check independent facts before desktop/narrow-viewport parity.
 * Author: Imitiyaz and AI Agent
 */
import { readFile, writeFile } from "node:fs/promises";
import { isDeepStrictEqual } from "node:util";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
const one = [
    ["page_1", "table_1_row_1", "BOLT-A", "10"],
    ["page_1", "table_1_row_2", "NUT-B", "6"],
  ],
  three = [
    ["page_3", "table_1_row_1", "BOLT-A", "4"],
    ["page_3", "table_1_row_2", "NUT-B", "8"],
  ];
const facts = {
  page1: ["answered", ["page_1"], "16", one],
  confirm: ["answered", ["page_1"], "16", one],
  page3: ["answered", ["page_3"], "12", three],
  back: ["answered", ["page_1"], "16", one],
  unknown: ["clarification_required", ["page_99"], null, []],
  tableless: ["clarification_required", ["page_2"], null, []],
  file: ["answered", [], "28", [...one, ...three]],
  return: ["answered", ["page_1"], "16", one],
  absent: ["no_evidence", [], null, []],
  fresh3: ["answered", ["page_3"], "12", three],
  fresh1: ["answered", ["page_1"], "16", one],
};
export function comparePageContracts(contracts) {
  const findings = [];
  if (
    !isDeepStrictEqual(contracts.map((c) => c.project).sort(), [
      "desktop",
      "mobile",
    ])
  )
    findings.push("Exactly one page contract per viewport required");
  for (const c of contracts) {
    if (
      !isDeepStrictEqual(
        Object.keys(c.checkpoints ?? {}).sort(),
        Object.keys(facts).sort(),
      )
    )
      findings.push("Wrong checkpoint coverage");
    for (const [key, [status, scope, result, records]] of Object.entries(
      facts,
    )) {
      const p = c.checkpoints?.[key];
      if (
        !p ||
        p.status !== status ||
        p.result !== result ||
        !isDeepStrictEqual(p.scope, scope) ||
        !isDeepStrictEqual(p.records, [...records].sort())
      ) {
        findings.push(`${key}: wrong scope/result/population`);
        continue;
      }
      if (
        !isDeepStrictEqual(
          p.operands,
          records.map(([s, r, , v]) => [s, r, v]).sort(),
        )
      )
        findings.push(`${key}: wrong operand population`);
      if (result !== null) {
        if (!new RegExp(`\\b${result}\\s+pcs\\b`).test(p.displayed))
          findings.push(`${key}: incorrect visible total`);
        const named = [...p.headline.matchAll(/page_(\d+)/g)].map(
          (m) => "page_" + m[1],
        );
        if (!isDeepStrictEqual([...new Set(named)].sort(), scope))
          findings.push(`${key}: contradictory effective question`);
        if (
          !p.headline.startsWith("Question: ") ||
          p.headline.includes("Use source records")
        )
          findings.push(`${key}: action replaced effective question`);
        if (!scope.every((s) => p.scopeText.includes(s)))
          findings.push(`${key}: wrong visible scope`);
      }
      if (
        ["confirm", "file"].includes(key) &&
        p.message !== "Your message: Use source records"
      )
        findings.push("Lost original user action");
      if (
        key === "absent" &&
        (!p.coverage?.includes("No matching source records") ||
          p.coverage.includes("Requested cells present"))
      )
        findings.push("No-match coverage claims cells present");
    }
  }
  if (
    contracts.length === 2 &&
    !isDeepStrictEqual(contracts[0].checkpoints, contracts[1].checkpoints)
  )
    findings.push("Desktop/mobile results differ");
  return findings;
}
export async function comparePageReport(path) {
  const report = JSON.parse(await readFile(path, "utf8"));
  const contracts = [],
    findings = [];
  async function walk(s) {
    for (const spec of s.specs ?? [])
      for (const t of spec.tests ?? []) {
        if (
          t.expectedStatus !== "passed" ||
          t.results.length !== 1 ||
          t.results[0].status !== "passed"
        )
          findings.push(
            "Failed/skipped/retried browser workflow: " + spec.title,
          );
        for (const r of t.results)
          for (const a of r.attachments ?? [])
            if (a.name === "page-scope-contract") {
              const c = JSON.parse(
                a.body
                  ? Buffer.from(a.body, "base64").toString("utf8")
                  : await readFile(a.path, "utf8"),
              );
              if (
                !c.run_id ||
                c.run_id !== report.config?.metadata?.verification_id
              )
                findings.push("Stale page contract");
              contracts.push(c);
            }
      }
    for (const child of s.suites ?? []) await walk(child);
  }
  for (const s of report.suites ?? []) await walk(s);
  findings.push(...comparePageContracts(contracts));
  return {
    status: findings.length ? "failed" : "passed",
    contracts,
    findings,
    method:
      "Independent source/page/operand facts and effective-question DOM checks, then viewport parity",
  };
}
if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  const out = process.argv[3] ?? "test-results/page-comparison.json";
  try {
    const r = await comparePageReport(
      process.argv[2] ?? "test-results/results.json",
    );
    await writeFile(out, JSON.stringify(r, null, 2) + "\n");
    console.log("PAGE COMPARISON:", r.status, out);
    process.exitCode = r.findings.length ? 1 : 0;
  } catch (e) {
    await writeFile(
      out,
      JSON.stringify({ status: "failed", findings: [String(e)] }, null, 2) +
        "\n",
    );
    console.error(String(e));
    process.exitCode = 1;
  }
}
