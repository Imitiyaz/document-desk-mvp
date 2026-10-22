/* SPDX-License-Identifier: AGPL-3.0-only */
/**
 * Render server-calculated values, missing-data states and navigable source links.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import type { Answer } from "./api";

// Group digits as text; JavaScript Number could round a server-computed Decimal result.
function groupedNumber(value: string) {
  const [whole, fraction] = value.split(".");
  return (
    whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") +
    (fraction === undefined ? "" : "." + fraction)
  );
}

export default function AnswerContent({
  answer,
  prefix = "",
}: {
  answer: Answer;
  prefix?: string;
}) {
  const identityField = answer.coverage.group_field || "Entity";
  // Citation targets may live inside collapsed evidence or historical cards; open their ancestors first.
  function reveal(number: number) {
    const target = document.getElementById(`${prefix}citation-${number}`);
    for (
      let node: HTMLElement | null = target;
      node;
      node = node.parentElement
    ) {
      if (node instanceof HTMLDetailsElement) node.open = true;
    }
    target?.focus({ preventScroll: true });
    target?.scrollIntoView?.({ block: "nearest" });
  }
  if (answer.grouped_results?.length) {
    return (
      <div className="readable-answer grouped-answer">
        {answer.coverage.population_basis === "all_selected_records" && (
          <p className="notice">
            Counting physical source records as confirmed. Repeated amounts on
            different sheets remain separate.
          </p>
        )}
        <p>
          Each group is calculated separately. Overall figures include every
          matching source record.
        </p>
        {answer.records.some(
          (r) => Object.keys(r.continuation_fields || {}).length > 0,
        ) && (
          <p className="notice">
            Region continuation rule applied. Evidence retains the original
            blank cells and the source label anchors. Missing revenue remains
            unknown.
          </p>
        )}
        <div className="table-wrap">
          <table>
            <caption>Grouped totals and available-value subtotals</caption>
            <thead>
              <tr>
                <th>Source scope</th>
                <th>Group</th>
                <th>Result</th>
                <th>Source records</th>
              </tr>
            </thead>
            <tbody>
              {answer.grouped_results.map((group, i) => (
                <tr key={i}>
                  <th scope="row">{group.scope}</th>
                  <td>{group.label}</td>
                  <td>
                    {group.calculation ? (
                      Object.entries(group.calculation.result).map(
                        ([field, value]) => (
                          <p key={field}>
                            {field}: <strong>{groupedNumber(value)}</strong>
                            {group.calculation?.unit
                              ? ` ${group.calculation.unit}`
                              : ""}
                            {group.status === "incomplete"
                              ? " · Available-value subtotal"
                              : " · Total"}
                          </p>
                        ),
                      )
                    ) : (
                      <p>
                        {group.status === "no_evidence"
                          ? "No matching source records; no zero inferred."
                          : "Calculation needs clarification."}
                      </p>
                    )}
                    {group.calculation?.excluded_cells?.map((e, index) => (
                      <p className="small" key={index}>
                        Missing {e.source.sheet_or_page} / {e.cell || e.field};
                        excluded.
                      </p>
                    ))}
                    {!!group.missing_entities.length && (
                      <p className="small">
                        No records for {group.missing_entities.join(", ")};
                        contribution unknown.
                      </p>
                    )}
                    {!!group.contributions?.length && (
                      <ul
                        className="contributor-details"
                        aria-label={`${identityField} contributions for ${group.scope} ${group.label}`}
                      >
                        {group.contributions.map((contribution, index) => (
                          <li key={index}>
                            <strong>
                              {contribution.entity ??
                                `${identityField} not recorded`}
                            </strong>
                            {": "}
                            {contribution.status === "no_evidence" ? (
                              <span>
                                No matching source records; contribution
                                unknown, not zero.
                              </span>
                            ) : contribution.calculation ? (
                              <span>
                                {Object.entries(contribution.calculation.result)
                                  .map(
                                    ([field, value]) =>
                                      `${field}: ${groupedNumber(value)}${contribution.calculation?.unit ? ` ${contribution.calculation.unit}` : ""}`,
                                  )
                                  .join("; ")}
                                {contribution.calculation.partial
                                  ? " · Available-value subtotal"
                                  : " · Total"}
                              </span>
                            ) : contribution.missing_cells.length ? (
                              <span>
                                Missing in source; contribution unknown, not
                                zero.
                              </span>
                            ) : (
                              <span>Calculation needs clarification.</span>
                            )}
                            {contribution.missing_cells.map(
                              (cell, cellIndex) => (
                                <span className="small" key={cellIndex}>
                                  {" "}
                                  {cell.field} missing at{" "}
                                  {cell.cell || "source location"}.
                                </span>
                              ),
                            )}
                            {contribution.record_numbers.map((n) => (
                              <a
                                key={n}
                                className="source-marker"
                                aria-label={`View source ${n} for ${group.scope} ${group.label} ${contribution.entity ?? "unlabelled record"}`}
                                href={`#${prefix}citation-${n}`}
                                onClick={() => reveal(n)}
                              >
                                [{n}]
                              </a>
                            ))}
                          </li>
                        ))}
                      </ul>
                    )}
                  </td>
                  <td>
                    {group.record_numbers.slice(0, 3).map((n) => (
                      <a
                        key={n}
                        className="source-marker"
                        aria-label={`View source ${n} for ${group.scope} ${group.label}`}
                        href={`#${prefix}citation-${n}`}
                        onClick={() => reveal(n)}
                      >
                        [{n}]
                      </a>
                    ))}
                    {group.record_numbers.length > 3 && (
                      <span>
                        {" "}
                        +{group.record_numbers.length - 3} records in evidence
                      </span>
                    )}
                    <details>
                      <summary>View this group’s calculation</summary>
                      <p>{group.answer}</p>
                      {group.calculation?.operands?.map((o) => (
                        <p key={o.number}>
                          [{o.number}] {o.source?.sheet_or_page} / row{" "}
                          {o.source?.row_or_location}:{" "}
                          {Object.entries(o.values)
                            .map(
                              ([f, v]) =>
                                `${f}: ${v} (${o.cell_references?.[f] || "table location"})`,
                            )
                            .join("; ")}
                        </p>
                      ))}
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }
  if (!answer.answer_items?.length) {
    return (
      <div className="answer-text">
        {answer.answer
          .split(/\n+/)
          .filter(Boolean)
          .map((line, i) => (
            <p key={i}>{line}</p>
          ))}
      </div>
    );
  }
  return (
    <div className="answer-text readable-answer">
      {answer.answer_items.map((item, index, items) => (
        <div key={index} className={`answer-statement ${item.kind}`}>
          {item.kind === "record" && item.scope !== items[index - 1]?.scope && (
            <h3>{item.scope}</h3>
          )}
          <p>
            <span>{item.text}</span>
            {item.citation_numbers.slice(0, 3).map((n) => (
              <a
                key={n}
                className="source-marker"
                aria-label={`View source ${n}`}
                href={`#${prefix}citation-${n}`}
                onClick={() => reveal(n)}
              >
                [{n}]
              </a>
            ))}
            {item.citation_numbers.length > 3 && (
              <a
                className="more-sources"
                href={`#${prefix ? `${prefix}evidence` : "answer-evidence"}`}
                onClick={() => {
                  const panel = document.getElementById(
                    prefix ? `${prefix}evidence` : "answer-evidence",
                  );
                  if (panel instanceof HTMLDetailsElement) panel.open = true;
                }}
              >
                {" "}
                +{item.citation_numbers.length - 3} source records in evidence
              </a>
            )}
          </p>
        </div>
      ))}
    </div>
  );
}
