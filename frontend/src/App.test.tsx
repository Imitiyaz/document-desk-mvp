/* SPDX-License-Identifier: AGPL-3.0-only */
/**
 * Verify App behavior.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { beforeEach, expect, test, vi } from "vitest";
import App from "./App";
import {
  sourceRecordsButtonName,
  documentLibraryReadyText,
  confirmationDialogRole,
  keepDataButtonName,
} from "../e2e/control-names";
import { api } from "./api";
import type { Answer, Source } from "./api";
vi.mock("./api", async (original) => ({
  ...(await original<typeof import("./api")>()),
  api: {
    list: vi.fn(),
    capabilities: vi.fn(),
    upload: vi.fn(),
    query: vi.fn(),
    workspace: vi.fn(),
    startConversation: vi.fn(),
    endConversation: vi.fn(),
    remove: vi.fn(),
    reset: vi.fn(),
  },
}));
const sources: Source[] = [
  {
    source_file: "sales.xlsx",
    document_id: "doc-1",
    workspace_revision: 0,
    state: "ready",
    ready: true,
    sha256: "test",
    sheets: [
      { name: "Merged Region", fields: ["Region", "Q3 Revenue"] },
      { name: "Sparse Data", fields: ["Region", "Q3 Revenue"] },
    ],
  },
];
const base: Answer = {
  status: "answered",
  execution_path: "structured",
  answer: "North: 45000 [1]",
  records: [
    {
      number: 1,
      source_file: "sales.xlsx",
      sheet_or_page: "Merged Region",
      row_or_location: 2,
      values: { Region: "North", "Q3 Revenue": "45000" },
      cell_references: { Region: "A2", "Q3 Revenue": "B2" },
      merged_fields: ["Region"],
    },
  ],
  citations: [
    {
      number: 1,
      source_file: "sales.xlsx",
      sheet_or_page: "Merged Region",
      row_or_location: 2,
      citation_text: "sales.xlsx / Merged Region / row 2",
    },
  ],
  coverage: { matched_records: 1, returned_records: 1, complete: true },
  calculation: null,
  warnings: [],
  unresolved_citation_numbers: [],
  timings_seconds: { total: 0.01 },
  model: null,
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.workspace).mockResolvedValue({ revision: 0 });
  vi.mocked(api.startConversation).mockResolvedValue({
    conversation_id: "chat-1",
  });
  vi.mocked(api.endConversation).mockResolvedValue({ status: "cleared" });
  vi.mocked(api.remove).mockResolvedValue({ workspace_revision: 1 });
  vi.mocked(api.reset).mockResolvedValue({ workspace_revision: 1 });
  vi.mocked(api.capabilities).mockResolvedValue({
    supported_extensions: [".pdf", ".xlsx", ".xlsm"],
    max_upload_bytes: 20 * 1024 * 1024,
  });
  vi.mocked(api.list).mockResolvedValue(sources);
  vi.mocked(api.query).mockResolvedValue(base);
});
async function ready() {
  render(<App />);
  await screen.findByRole("option", { name: "sales.xlsx" });
}
function submit(text = "What was the Q3 revenue for North?") {
  fireEvent.change(screen.getByLabelText("Your question"), {
    target: { value: text },
  });
  fireEvent.click(screen.getByRole("button", { name: /Find answer/ }));
}

test("clarification current card never inherits an earlier answer's source evidence", async () => {
  vi.mocked(api.query)
    .mockResolvedValueOnce({ ...base, context_token: "value-token" })
    .mockResolvedValueOnce({
      ...base,
      status: "clarification_required",
      execution_path: "structured",
      answer: "Unrecognized words: unicorn. Rephrase that part.",
      records: [],
      citations: [],
      coverage: {},
      context_token: "pending-token",
    })
    .mockResolvedValueOnce({
      ...base,
      status: "clarification_required",
      execution_path: "conversation_clarification",
      answer:
        "Question awaiting clarification: SUM Q3 Revenue. Rephrase unicorn.",
      records: [],
      citations: [],
      coverage: {},
      context_token: "explained-token",
    });
  await ready();
  submit();
  await screen.findByText("North: 45000 [1]");
  submit("Sum Q3 Revenue using unicorn");
  await screen.findByText("Unrecognized words: unicorn. Rephrase that part.");
  submit("what clarification you need ?");
  await screen.findByText(
    "Question awaiting clarification: SUM Q3 Revenue. Rephrase unicorn.",
  );
  const current = screen.getByRole("region", { name: "Answer" });
  expect(within(current).queryByText(/View evidence/)).not.toBeInTheDocument();
  expect(
    within(current).queryByText("sales.xlsx / Merged Region / row 2"),
  ).not.toBeInTheDocument();
  expect(vi.mocked(api.query).mock.calls[2][0]).toEqual(
    expect.objectContaining({
      conversation_id: "chat-1",
      context_token: "pending-token",
      question: "what clarification you need ?",
    }),
  );
  expect(
    screen.getByRole("region", { name: "Earlier conversation" }),
  ).toBeInTheDocument();
});

test("a contributor citation outside the displayed evidence page still opens its source", async () => {
  vi.mocked(api.query).mockResolvedValue({
    ...base,
    citations: [
      ...base.citations,
      {
        ...base.citations[0],
        number: 51,
        row_or_location: 52,
        citation_text: "sales.xlsx / Merged Region / row 52",
      },
    ],
    grouped_results: [
      {
        label: "Overall",
        scope: "Whole file",
        entities: [],
        status: "answered",
        answer: "45,000",
        record_numbers: [1, 51],
        missing_entities: [],
        calculation: {
          operation: "sum",
          result: { "Q3 Revenue": "45000" },
          unit: "",
        },
        contributions: [
          {
            entity: "North",
            status: "answered",
            record_numbers: [51],
            missing_cells: [],
            calculation: {
              operation: "sum",
              result: { "Q3 Revenue": "45000" },
              unit: "",
            },
          },
        ],
      },
    ],
  });
  await ready();
  submit();
  const link = await screen.findByRole("link", {
    name: "View source 51 for Whole file Overall North",
  });
  fireEvent.click(link);
  const target = document.getElementById("citation-51");
  expect(target).toHaveFocus();
  expect(target).toHaveTextContent("row 52");
});
test("empty question disabled and source list persists in UI", async () => {
  await ready();
  expect(screen.getByRole("button", { name: /Find answer/ })).toBeDisabled();
  expect(screen.getByText("1 indexed document")).toBeInTheDocument();
});
test("submits exact question and selected scope; displays source cells and coverage", async () => {
  await ready();
  fireEvent.change(screen.getByLabelText("Sheet or page"), {
    target: { value: "Merged Region" },
  });
  submit();
  await screen.findByRole("region", { name: "Answer" });
  expect(api.query).toHaveBeenCalledWith(
    expect.objectContaining({
      question: "What was the Q3 revenue for North?",
      source_file: "sales.xlsx",
      sheet_or_page: "Merged Region",
    }),
    expect.any(AbortSignal),
  );
  expect(screen.getByText("B2")).toBeInTheDocument();
  expect(screen.getByText(/1 of 1 matching records/)).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "[1] Merged Region" }),
  ).toHaveAttribute("href", "#citation-1");
});
test("clarification resubmits a source choice without inventing a numeric answer", async () => {
  vi.mocked(api.query).mockResolvedValueOnce({
    ...base,
    status: "clarification_required",
    answer: "Choose one sheet.",
    records: [],
    citations: [],
    coverage: { available_scopes: ["Sparse Data"] },
    clarification_options: [
      { label: "Sparse Data", sheet_or_page: "Sparse Data" },
    ],
  });
  vi.mocked(api.query).mockResolvedValue({
    ...base,
    answer: "Scoped source answer",
  });
  await ready();
  submit("What was the Q3 revenue?");
  await screen.findByText("Choose one sheet.");
  fireEvent.click(screen.getByRole("button", { name: "Sparse Data →" }));
  expect(screen.getByLabelText("Sheet or page")).toHaveValue("");
  await screen.findByText("Scoped source answer");
  expect(api.query).toHaveBeenCalledTimes(2);
  expect(vi.mocked(api.query).mock.calls[1][0].sheet_or_page).toBe(
    "Sparse Data",
  );
});
test("blank cells are visible and no calculation is invented", async () => {
  vi.mocked(api.query).mockResolvedValue({
    ...base,
    status: "incomplete",
    records: [
      { ...base.records[0], values: { Region: null, "Q3 Revenue": null } },
    ],
    coverage: { matched_records: 1, returned_records: 1, complete: false },
  });
  await ready();
  submit();
  await screen.findByText("Incomplete answer");
  expect(screen.getAllByText("Missing in source")).toHaveLength(2);
  expect(screen.queryByText(/CALCULATION/)).not.toBeInTheDocument();
});
test("rejects unsupported and oversized uploads before network call", async () => {
  await ready();
  const input = screen.getByLabelText("Upload document");
  fireEvent.change(input, {
    target: { files: [new File(["abc"], "legacy.xls")] },
  });
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Re-save legacy XLS",
  );
  const large = new File(["a"], "big.xlsx");
  Object.defineProperty(large, "size", { value: 21 * 1024 * 1024 });
  fireEvent.change(input, { target: { files: [large] } });
  expect(screen.getByRole("alert")).toHaveTextContent("up to 20 MB");
  expect(api.upload).not.toHaveBeenCalled();
});
test("duplicate/server errors are shown; pending state prevents double-submit", async () => {
  vi.mocked(api.query).mockRejectedValue(new Error("Duplicate error test"));
  await ready();
  submit();
  await screen.findByRole("alert");
  expect(screen.getByRole("alert")).toHaveTextContent("Duplicate error test");
  expect(
    screen.getByRole("button", { name: /Find answer/ }),
  ).not.toBeDisabled();
});
test("cancellation aborts request and cannot show a stale answer", async () => {
  let complete!: (a: Answer) => void;
  vi.mocked(api.query).mockImplementation(
    () =>
      new Promise((resolve) => {
        complete = resolve;
      }),
  );
  await ready();
  submit();
  await screen.findByText(
    "Checking your question against the selected document…",
  );
  fireEvent.click(screen.getByRole("button", { name: "Stop waiting" }));
  expect(vi.mocked(api.query).mock.calls[0][1]?.aborted).toBe(true);
  complete(base);
  await waitFor(() =>
    expect(
      screen.queryByRole("region", { name: "Answer" }),
    ).not.toBeInTheDocument(),
  );
});
test("renders document text as text, never executable HTML", async () => {
  vi.mocked(api.query).mockResolvedValue({
    ...base,
    answer: '<img src=x onerror="alert(1)"> [1]',
  });
  await ready();
  submit();
  await screen.findByText('<img src=x onerror="alert(1)"> [1]');
  expect(document.querySelector("img")).toBeNull();
});
test("successful upload refreshes list and selects new source", async () => {
  vi.mocked(api.upload).mockResolvedValue({
    source_file: "new.pdf",
    chunks_stored: 3,
  });
  await ready();
  vi.mocked(api.list).mockResolvedValue([
    ...sources,
    { ...sources[0], source_file: "new.pdf" },
  ]);
  fireEvent.change(screen.getByLabelText("Upload document"), {
    target: {
      files: [new File(["pdf"], "new.pdf", { type: "application/pdf" })],
    },
  });
  await screen.findByText(/new.pdf indexed/);
  expect(screen.getByLabelText("Document")).toHaveValue("new.pdf");
});

test("explicit fields, operation and equality filter are transmitted together", async () => {
  await ready();
  fireEvent.click(
    screen.getByText("Set fields, calculation or equality filter"),
  );
  fireEvent.change(screen.getByLabelText("Operation"), {
    target: { value: "sum" },
  });
  fireEvent.click(screen.getByLabelText("Q3 Revenue", { selector: "input" }));
  fireEvent.change(screen.getByLabelText("Filter field"), {
    target: { value: "Region" },
  });
  fireEvent.change(screen.getByLabelText("Filter value"), {
    target: { value: "North" },
  });
  submit();
  await screen.findByRole("region", { name: "Answer" });
  expect(api.query).toHaveBeenCalledWith(
    expect.objectContaining({
      operation: "sum",
      fields: ["Q3 Revenue"],
      filters: { Region: "North" },
    }),
    expect.any(AbortSignal),
  );
});

test("selected filter needs a value and changing document scope resets it", async () => {
  await ready();
  fireEvent.change(screen.getByLabelText("Filter field"), {
    target: { value: "Region" },
  });
  submit();
  expect(await screen.findByRole("alert")).toHaveTextContent("Enter a value");
  expect(api.query).not.toHaveBeenCalled();
  fireEvent.change(screen.getByLabelText("Sheet or page"), {
    target: { value: "Sparse Data" },
  });
  expect(screen.getByLabelText("Filter field")).toHaveValue("");
  expect(screen.getByLabelText("Operation")).toHaveValue("auto");
});

test("initial connection failure can recover through Refresh", async () => {
  vi.mocked(api.list).mockRejectedValueOnce(new Error("API offline"));
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("API offline");
  fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
  await screen.findByRole("option", { name: "sales.xlsx" });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
});

test("unresolved references are prominently flagged rather than hidden", async () => {
  vi.mocked(api.query).mockResolvedValue({
    ...base,
    unresolved_citation_numbers: [999],
  });
  await ready();
  submit();
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Unresolved source markers: 999",
  );
});

test("an uploaded file is not reported as a failed upload when the following refresh fails", async () => {
  vi.mocked(api.upload).mockResolvedValue({
    source_file: "new.pdf",
    chunks_stored: 1,
  });
  await ready();
  vi.mocked(api.list).mockRejectedValue(new Error("Connection interrupted"));
  fireEvent.change(screen.getByLabelText("Upload document"), {
    target: { files: [new File(["data"], "new.pdf")] },
  });
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Upload completed, but the document list could not refresh",
  );
  expect(api.upload).toHaveBeenCalledTimes(1);
});

test("derived values link to their particular source record, while sums keep field labels", async () => {
  vi.mocked(api.query).mockResolvedValue({
    ...base,
    calculation: { operation: "increase", result: { "1": "7000" }, unit: "" },
  });
  await ready();
  submit("What was the increase?");
  const link = await screen.findByRole("link", {
    name: "Merged Region · row 2 · Source [1]",
  });
  expect(link).toHaveAttribute("href", "#citation-1");
  expect(link.closest("p")).toHaveTextContent("7000");
  vi.mocked(api.query).mockResolvedValue({
    ...base,
    calculation: {
      operation: "sum",
      result: { "Q3 Revenue": "45000" },
      unit: "",
    },
  });
  submit("What was the total?");
  await waitFor(() =>
    expect(
      screen.getByText("Q3 Revenue", { selector: ".calculation span" }),
    ).toBeInTheDocument(),
  );
});

test("whole-document default keeps optional refinements collapsed", async () => {
  await ready();
  expect(
    screen.getByText("Refine sources — optional").closest("details"),
  ).not.toHaveAttribute("open");
  expect(screen.getByText(/Searching the whole document/)).toBeInTheDocument();
  submit();
  await screen.findByRole("region", { name: "Answer" });
  expect(vi.mocked(api.query).mock.calls[0][0].sheet_or_page).toBeUndefined();
});
test("New chat clears answers and refinements while preserving uploads", async () => {
  await ready();
  submit();
  await screen.findByRole("region", { name: "Answer" });
  fireEvent.click(screen.getByRole("button", { name: "New chat" }));
  expect(
    screen.queryByRole("region", { name: "Answer" }),
  ).not.toBeInTheDocument();
  expect(screen.getByLabelText("Your question")).toHaveValue("");
  expect(api.endConversation).toHaveBeenCalledWith("chat-1");
  expect(api.remove).not.toHaveBeenCalled();
  expect(
    screen.getByRole("option", { name: "sales.xlsx" }),
  ).toBeInTheDocument();
});
test("follow-ups send the acknowledged context and retain earlier source answers", async () => {
  vi.mocked(api.query)
    .mockResolvedValueOnce({ ...base, context_token: "ack-1" })
    .mockResolvedValueOnce({ ...base, context_token: "ack-2" });
  await ready();
  submit();
  await screen.findByRole("region", { name: "Answer" });
  submit("And South?");
  await screen.findByRole("region", { name: "Earlier conversation" });
  expect(vi.mocked(api.query).mock.calls[1][0].context_token).toBe("ack-1");
});
test("removal confirmation supports Escape and restores focus without deleting", async () => {
  await ready();
  const remove = screen.getByRole("button", { name: "Remove sales.xlsx" });
  remove.focus();
  fireEvent.click(remove);
  expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Keep data" })).toHaveFocus();
  fireEvent.keyDown(screen.getByRole("button", { name: "Keep data" }), {
    key: "Escape",
  });
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  expect(remove).toHaveFocus();
  expect(api.remove).not.toHaveBeenCalled();
});
test("confirmed selective deletion preserves another document", async () => {
  const other = {
    ...sources[0],
    source_file: "other.xlsx",
    document_id: "doc-2",
  };
  vi.mocked(api.list)
    .mockResolvedValueOnce([...sources, other])
    .mockResolvedValue([other]);
  await ready();
  fireEvent.click(screen.getByRole("button", { name: "Remove sales.xlsx" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm removal" }));
  await screen.findByText("sales.xlsx removed from this workspace.");
  expect(screen.getByLabelText("Document")).toHaveValue("other.xlsx");
  expect(
    screen.queryByRole("option", { name: "sales.xlsx" }),
  ).not.toBeInTheDocument();
});
test("workspace reset confirms affected count and returns to upload state", async () => {
  await ready();
  vi.mocked(api.list).mockResolvedValue([]);
  fireEvent.click(screen.getByRole("button", { name: "Reset workspace" }));
  expect(screen.getByRole("alertdialog")).toHaveTextContent(
    "all 1 indexed documents",
  );
  fireEvent.click(screen.getByRole("button", { name: "Confirm removal" }));
  await screen.findByText("Workspace reset. Upload a document to begin.");
  expect(api.reset).toHaveBeenCalledWith(0);
  expect(screen.getByText("0 indexed documents")).toBeInTheDocument();
});
test("desktop reset cancellation contract preserves documents and the current answer", async () => {
  await ready();
  submit();
  const answer = await screen.findByRole("region", { name: "Answer" });
  const answerBefore = answer.textContent;
  const reset = screen.getByRole("button", { name: "Reset workspace" });
  reset.focus();
  fireEvent.click(reset);
  const confirmation = screen.getByRole(confirmationDialogRole);
  expect(confirmation).toHaveTextContent("all 1 indexed documents");
  const keep = within(confirmation).getByRole("button", {
    name: keepDataButtonName,
  });
  expect(keep).toHaveFocus();
  fireEvent.click(keep);
  expect(screen.queryByRole(confirmationDialogRole)).not.toBeInTheDocument();
  expect(reset).toHaveFocus();
  expect(screen.getByLabelText("Document")).toHaveValue("sales.xlsx");
  expect(screen.getByRole("region", { name: "Answer" }).textContent).toBe(
    answerBefore,
  );
  expect(api.reset).not.toHaveBeenCalled();
  expect(api.remove).not.toHaveBeenCalled();
});
test("typing the next draft while a request is running preserves it", async () => {
  let finish!: (answer: Answer) => void;
  vi.mocked(api.query).mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  await ready();
  submit();
  await waitFor(() => expect(api.query).toHaveBeenCalledTimes(1));
  fireEvent.change(screen.getByLabelText("Your question"), {
    target: { value: "And South?" },
  });
  finish({ ...base, context_token: "ack" });
  await screen.findByRole("region", { name: "Answer" });
  expect(screen.getByLabelText("Your question")).toHaveValue("And South?");
});

test("a cancelled later answer cannot replace the acknowledged conversation context", async () => {
  let finish!: (answer: Answer) => void;
  vi.mocked(api.query)
    .mockResolvedValueOnce({ ...base, context_token: "acknowledged" })
    .mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    )
    .mockResolvedValueOnce({ ...base, context_token: "next" });
  await ready();
  submit();
  await screen.findByRole("region", { name: "Answer" });
  submit("And South?");
  await waitFor(() => expect(api.query).toHaveBeenCalledTimes(2));
  fireEvent.click(screen.getByRole("button", { name: "Stop waiting" }));
  finish({ ...base, answer: "unseen answer", context_token: "unseen" });
  submit("And East?");
  await waitFor(() => expect(api.query).toHaveBeenCalledTimes(3));
  expect(vi.mocked(api.query).mock.calls[2][0].context_token).toBe(
    "acknowledged",
  );
  expect(screen.queryByText("unseen answer")).not.toBeInTheDocument();
});
test("failed deletion remains visible and pending data cannot be queried", async () => {
  await ready();
  vi.mocked(api.remove).mockRejectedValue(
    new Error("Removal pending; retry removal."),
  );
  vi.mocked(api.list).mockResolvedValue([
    { ...sources[0], ready: false, state: "deleting" },
  ]);
  vi.mocked(api.workspace).mockResolvedValue({ revision: 1 });
  fireEvent.click(screen.getByRole("button", { name: "Remove sales.xlsx" }));
  fireEvent.click(screen.getByRole("button", { name: "Confirm removal" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Removal pending");
  expect(screen.getByRole("button", { name: /Find answer/ })).toBeDisabled();
});

test("readable answer is primary, evidence is collapsed, and a new question collapses it again", async () => {
  vi.mocked(api.query).mockResolvedValue({
    ...base,
    answer_items: [
      {
        kind: "record",
        text: "North — Q3 Revenue: 45,000",
        citation_numbers: [1],
        scope: "Merged Region",
        record_number: 1,
      },
    ],
  });
  await ready();
  submit();
  await screen.findByText("North — Q3 Revenue: 45,000");
  const details = screen
    .getByText(/View evidence \(1 source record\)/)
    .closest("details");
  expect(details).not.toHaveAttribute("open");
  expect(screen.getByText("B2")).not.toBeVisible();
  fireEvent.click(screen.getByRole("link", { name: "View source 1" }));
  expect(details).toHaveAttribute("open");
  expect(screen.getByText("B2")).toBeVisible();
  expect(document.getElementById("citation-1")).toHaveFocus();
  submit("What about another field?");
  await waitFor(() =>
    expect(
      screen.getByText(/Question: What about another field/),
    ).toBeInTheDocument(),
  );
  expect(
    screen.getByText(/View evidence \(1 source record\)/).closest("details"),
  ).not.toHaveAttribute("open");
});

test("clarification source choice applies to one turn and does not pin the next question", async () => {
  vi.mocked(api.query)
    .mockResolvedValueOnce({
      ...base,
      status: "clarification_required",
      answer: "Choose sources",
      clarification_options: [
        { label: "Sparse Data", sheet_or_page: "Sparse Data" },
      ],
    })
    .mockResolvedValueOnce({
      ...base,
      answer: "Available subtotal: 146,000",
      coverage: { ...base.coverage, resolved_scopes: ["Sparse Data"] },
    })
    .mockResolvedValueOnce(base);
  await ready();
  submit("SUM Q3 Revenue in the file");
  fireEvent.click(await screen.findByRole("button", { name: "Sparse Data →" }));
  await screen.findByText("Available subtotal: 146,000");
  expect(screen.getByLabelText("Sheet or page")).toHaveValue("");
  expect(vi.mocked(api.query).mock.calls[1][0].sheet_or_page).toBe(
    "Sparse Data",
  );
  submit("What was Q3 Revenue for North in Merged Region?");
  await waitFor(() => expect(api.query).toHaveBeenCalledTimes(3));
  expect(vi.mocked(api.query).mock.calls[2][0].sheet_or_page).toBeUndefined();
});

test("subtotal and missing coverage stay visible when evidence is collapsed", async () => {
  vi.mocked(api.query).mockResolvedValue({
    ...base,
    status: "incomplete",
    answer: "Available-value subtotal Q3 Revenue: 146,000.",
    coverage: {
      matched_records: 5,
      returned_records: 5,
      complete: false,
      resolved_scopes: ["Sparse Data"],
    },
    calculation: {
      operation: "sum",
      partial: true,
      result: { "Q3 Revenue": "146000" },
      unit: "",
      operands: [
        [1, "45000"],
        [2, "38000"],
        [4, "41000"],
        [5, "22000"],
      ].map(([number, value]) => ({
        number: Number(number),
        values: { "Q3 Revenue": String(value) },
      })),
      excluded_cells: [
        {
          number: 3,
          field: "Q3 Revenue",
          cell: "B4",
          reason: "missing_value",
          source: {
            source_file: "sales.xlsx",
            sheet_or_page: "Sparse Data",
            row_or_location: 4,
          },
        },
      ],
    },
  });
  await ready();
  submit("SUM Q3 Revenue");
  expect(
    await screen.findByText("Available-value subtotal Q3 Revenue: 146,000."),
  ).toBeVisible();
  expect(screen.getByText(/Subtotal uses 4 of 5 source records/)).toBeVisible();
  expect(screen.getByText("Source scope used: Sparse Data")).toBeVisible();
  expect(
    screen.getByText(/View evidence/).closest("details"),
  ).not.toHaveAttribute("open");
  expect(screen.queryByText(/Calculation uses all 5/)).not.toBeInTheDocument();
});

test("browser source-record selector finds the rendered choice and submits its actual confirmation", async () => {
  vi.mocked(api.query)
    .mockResolvedValueOnce({
      ...base,
      status: "clarification_required",
      answer: "Choose the physical-record counting basis.",
      records: [],
      citations: [],
      coverage: {},
      context_token: "counting-pending-token",
      clarification_options: [
        {
          label: "Use source records",
          aggregation_basis: "all_selected_records",
        },
      ],
    })
    .mockResolvedValueOnce({
      ...base,
      answer: "Confirmed source-record answer.",
    });
  await ready();
  submit("SUM Q3 Revenue across the source records");
  const current = await screen.findByRole("region", {
    name: "Answer",
  });
  await within(current).findByText(
    "Choose the physical-record counting basis.",
  );
  // The previous exact selector omitted the visible arrow and matched nothing.
  expect(
    within(current).queryByRole("button", {
      name: "Use source records",
    }),
  ).not.toBeInTheDocument();
  const choice = within(current).getByRole("button", {
    name: sourceRecordsButtonName,
  });
  expect(choice).toBeEnabled();
  fireEvent.click(choice);
  await screen.findByText("Confirmed source-record answer.");
  expect(api.query).toHaveBeenCalledTimes(2);
  const payload = vi.mocked(api.query).mock.calls[1][0];
  expect(payload).toEqual(
    expect.objectContaining({
      question: "Use source records",
      aggregation_basis: "all_selected_records",
      conversation_id: "chat-1",
      context_token: "counting-pending-token",
    }),
  );
  expect(payload).not.toHaveProperty("group_field");
  expect(payload).not.toHaveProperty("entity_groups");
});

test("effective question is visible and literal confirmation remains in history", async () => {
  const effective = "Total Q3 Revenue in Merged Region";
  vi.mocked(api.query)
    .mockResolvedValueOnce({
      ...base,
      resolved_question: effective,
      status: "clarification_required",
      answer: "Confirm physical records.",
      records: [],
      citations: [],
      context_token: "pending-effective",
      clarification_options: [
        {
          label: "Use source records",
          aggregation_basis: "all_selected_records",
        },
      ],
    })
    .mockResolvedValueOnce({
      ...base,
      resolved_question: effective,
      answer: "Confirmed scoped result.",
    })
    .mockResolvedValueOnce({
      ...base,
      resolved_question: "Total Q3 Revenue in Sparse Data",
      answer: "Changed scoped result.",
    });
  await ready();
  submit(effective);
  fireEvent.click(
    await screen.findByRole("button", { name: sourceRecordsButtonName }),
  );
  await screen.findByText("Confirmed scoped result.");
  const current = screen.getByRole("region", { name: "Answer" });
  expect(
    within(current).getByText("Question: " + effective),
  ).toBeInTheDocument();
  expect(
    within(current).getByText("Your message: Use source records"),
  ).toBeInTheDocument();
  submit("Sparse Data");
  await screen.findByText("Changed scoped result.");
  expect(
    within(current).getByText("Question: Total Q3 Revenue in Sparse Data"),
  ).toBeInTheDocument();
  expect(
    within(current).getByText("Your message: Sparse Data"),
  ).toBeInTheDocument();
  expect(
    within(
      screen.getByRole("region", { name: "Earlier conversation" }),
    ).getByText("Use source records"),
  ).toBeInTheDocument();
});

test("no-match coverage cannot claim requested cells present", async () => {
  vi.mocked(api.query).mockResolvedValue({
    ...base,
    status: "no_evidence",
    answer: "No matching Product records for Apple.",
    records: [],
    citations: [],
    coverage: { matched_records: 0, returned_records: 0, complete: true },
  });
  await ready();
  submit("Quantity for Apple?");
  await screen.findByText("No matching Product records for Apple.");
  const current = screen.getByRole("region", { name: "Answer" });
  expect(
    within(current).getByText(/No matching source records/),
  ).toBeInTheDocument();
  expect(
    within(current).queryByText(/Requested cells present/),
  ).not.toBeInTheDocument();
});

test("browser fixture setup waits for the asynchronously loaded document library", async () => {
  let release!: (value: Source[]) => void;
  vi.mocked(api.list).mockReturnValue(
    new Promise<Source[]>((resolve) => {
      release = resolve;
    }),
  );
  const { container } = render(<App />);
  const caption = container.querySelector(".library-caption")!;
  expect(caption.textContent).toBe("Loading documents…");
  expect(caption.textContent).not.toMatch(documentLibraryReadyText);
  expect(screen.getByLabelText("Upload document")).toBeDisabled();
  expect(
    screen.queryByRole("button", { name: "Remove sales.xlsx" }),
  ).not.toBeInTheDocument();
  release(sources);
  await waitFor(() =>
    expect(caption.textContent).toMatch(documentLibraryReadyText),
  );
  expect(
    screen.getByRole("button", { name: "Remove sales.xlsx" }),
  ).toBeInTheDocument();
  expect(screen.getByLabelText("Upload document")).toBeEnabled();
});
