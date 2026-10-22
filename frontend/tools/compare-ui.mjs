/**
 * Fail closed on incomplete runs or disagreeing desktop/mobile result contracts.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
/** Fail closed on missing runs, failed/skipped tests or desktop/mobile disagreement. */
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { isDeepStrictEqual } from "node:util";

export function compareContracts(contracts) {
  const findings = [];
  const projects = contracts.map((c) => c.project).sort();
  if (!isDeepStrictEqual(projects, ["desktop", "mobile"]))
    findings.push("Exactly one desktop and one mobile contract are required.");
  // Check each viewport against reviewed facts first; two identical wrong answers must fail.
  const reference = [
    ["Whole file", "Overall", "315,000", true],
    ["Whole file", "East + West", "63,000", true],
    ["Whole file", "North + South", "252,000", false],
    ["Merged Region", "Overall", "169,000", false],
    ["Merged Region", "East + West", null, null],
    ["Merged Region", "North + South", "169,000", false],
    ["Sparse Data", "Overall", "146,000", true],
    ["Sparse Data", "East + West", "63,000", true],
    ["Sparse Data", "North + South", "83,000", true],
  ];
  const sourceNumbers = {
    "Whole file": {
      North: [1, 2, 5, 6],
      South: [3, 4],
      East: [7],
      West: [8, 9],
    },
    "Merged Region": { North: [1, 2], South: [3, 4], East: [], West: [] },
    "Sparse Data": { North: [5, 6], South: [], East: [7], West: [8, 9] },
  };
  const amounts = {
    "Whole file": { North: "175,000", South: "77,000", West: "63,000" },
    "Merged Region": { North: "92,000", South: "77,000" },
    "Sparse Data": { North: "83,000", West: "63,000" },
  };
  for (const contract of contracts) {
    const p = contract.project;
    if (contract.scenario !== "contributor-correction")
      findings.push(`${p}: wrong scenario.`);
    if (
      !isDeepStrictEqual(Object.keys(contract.checkpoints ?? {}).sort(), [
        "confirmed",
        "corrected",
        "fresh_question",
        "new_chat",
      ])
    )
      findings.push(`${p}: missing/extra checkpoints.`);
    for (const checkpoint of ["confirmed", "corrected"]) {
      const groups = contract.checkpoints?.[checkpoint]?.groups ?? [];
      if (groups.length !== reference.length)
        findings.push(`${p}/${checkpoint}: missing grouped results.`);
      for (const [i, [scope, label, amount, partial]] of reference.entries()) {
        const g = groups[i];
        if (!g || g.scope !== scope || g.label !== label) {
          findings.push(`${p}/${checkpoint}: wrong group ${i}.`);
          continue;
        }
        if (
          amount === null
            ? !g.result.includes(
                "No matching source records; no zero inferred.",
              )
            : !g.result.startsWith(
                `Q3 Revenue: ${amount} · ${partial ? "Available-value subtotal" : "Total"}`,
              )
        )
          findings.push(
            `${p}/${checkpoint}: wrong visible result ${scope}/${label}.`,
          );
        const names =
          label === "Overall"
            ? scope === "Merged Region"
              ? ["North", "South"]
              : ["North", "South", "East", "West"].filter(
                  (n) => scope !== "Sparse Data" || n !== "South",
                )
            : label.split(" + ");
        if (
          !isDeepStrictEqual(
            g.contributors?.map((c) => c.entity),
            names,
          )
        )
          findings.push(
            `${p}/${checkpoint}: omitted contributor ${scope}/${label}.`,
          );
        for (const c of g.contributors ?? []) {
          if (!isDeepStrictEqual(c.sources, sourceNumbers[scope][c.entity]))
            findings.push(
              `${p}/${checkpoint}: wrong or missing contributor citations.`,
            );
          const absent =
            (scope === "Merged Region" &&
              ["East", "West"].includes(c.entity)) ||
            (scope === "Sparse Data" && c.entity === "South");
          if (
            absent &&
            (!c.text.includes(
              "No matching source records; contribution unknown, not zero.",
            ) ||
              c.sources.length)
          )
            findings.push(
              `${p}/${checkpoint}: absent entity changed to a number.`,
            );
          if (
            !absent &&
            c.entity === "East" &&
            (!c.text.includes("Missing in source") ||
              !c.text.includes("missing at B4"))
          )
            findings.push(
              `${p}/${checkpoint}: East's missing revenue was hidden.`,
            );
          if (
            !absent &&
            c.entity !== "East" &&
            !c.text.startsWith(
              `${c.entity}: Q3 Revenue: ${amounts[scope][c.entity]} · Total`,
            )
          )
            findings.push(
              `${p}/${checkpoint}: incorrect visible contributor amount.`,
            );
        }
      }
      const citations = contract.checkpoints?.[checkpoint]?.citations;
      if (
        !isDeepStrictEqual(citations, [
          [1, "Merged Region", 2],
          [2, "Merged Region", 3],
          [3, "Merged Region", 4],
          [4, "Merged Region", 5],
          [5, "Sparse Data", 2],
          [6, "Sparse Data", 3],
          [7, "Sparse Data", 4],
          [8, "Sparse Data", 5],
          [9, "Sparse Data", 6],
        ])
      )
        findings.push(`${p}/${checkpoint}: incomplete source references.`);
    }
    if (
      contract.checkpoints?.fresh_question?.requires_confirmation !== true ||
      contract.checkpoints?.fresh_question?.evidence_count !== 0
    )
      findings.push(
        `${p}: a fresh question silently borrowed a counting approval.`,
      );
    if (
      contract.checkpoints?.new_chat?.evidence_count !== 0 ||
      contract.checkpoints?.new_chat?.message !==
        "There is no pending clarification in this chat"
    )
      findings.push(`${p}: new chat inherited evidence or clarification.`);
  }
  if (
    contracts.length === 2 &&
    !isDeepStrictEqual(contracts[0].checkpoints, contracts[1].checkpoints)
  )
    findings.push(
      "Desktop/mobile values, warnings, contributors or citations differ.",
    );
  return findings;
}

export async function compareReport(path) {
  const report = JSON.parse(
    (await readFile(path, "utf8")).replace(/^\uFEFF/, ""),
  );
  const findings = [],
    contracts = [],
    testNames = { desktop: [], mobile: [] };
  async function walk(suite) {
    for (const spec of suite.specs ?? [])
      for (const test of spec.tests ?? []) {
        if (!testNames[test.projectName]) {
          findings.push("Unexpected browser project: " + test.projectName);
          continue;
        }
        testNames[test.projectName].push(spec.title);
        if (
          test.expectedStatus !== "passed" ||
          test.results.length !== 1 ||
          test.results[0].status !== "passed"
        )
          findings.push(
            `${test.projectName}: failed, retried or skipped test: ${spec.title}`,
          );
        for (const result of test.results)
          for (const attachment of result.attachments ?? [])
            if (attachment.name === "ui-contract") {
              const contract = JSON.parse(
                attachment.body
                  ? Buffer.from(attachment.body, "base64").toString("utf8")
                  : await readFile(attachment.path, "utf8"),
              );
              if (
                !contract.run_id ||
                contract.run_id !== report.config?.metadata?.verification_id
              )
                findings.push("Stale or mismatched UI contract run identity.");
              contracts.push(contract);
            }
      }
    for (const child of suite.suites ?? []) await walk(child);
  }
  for (const suite of report.suites ?? []) await walk(suite);
  if (
    !testNames.desktop.length ||
    !isDeepStrictEqual(testNames.desktop.sort(), testNames.mobile.sort())
  )
    findings.push("Desktop/mobile workflow coverage differs or is empty.");
  findings.push(...compareContracts(contracts));
  return {
    status: findings.length ? "failed" : "passed",
    run_id: report.config?.metadata?.verification_id,
    method:
      "Actual rendered values/warnings/contributors/citations vs reviewed fixture expectations and desktop/mobile equality; Chromium viewport emulation, not a physical phone or pixel-diff certification.",
    workflows_per_project: testNames.desktop.length,
    contracts,
    findings,
  };
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(resolve(process.argv[1])).href
) {
  const args = process.argv.slice(2),
    input = args[0] || "test-results/results.json",
    output = args[1] || "test-results/ui-comparison.json";
  try {
    const report = await compareReport(input);
    await writeFile(output, JSON.stringify(report, null, 2) + "\n");
    console.log(`UI COMPARISON: ${report.status}; ${output}`);
    for (const finding of report.findings) console.error(finding);
    process.exitCode = report.findings.length ? 1 : 0;
  } catch (error) {
    await writeFile(
      output,
      JSON.stringify({ status: "failed", findings: [String(error)] }, null, 2) +
        "\n",
    );
    console.error(String(error));
    process.exitCode = 1;
  }
}
