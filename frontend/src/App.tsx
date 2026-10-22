/* SPDX-License-Identifier: AGPL-3.0-only */
/**
 * Coordinate document selection, acknowledged chat requests and safe lifecycle actions.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import { useEffect, useRef, useState } from "react";
import { api, errorMessage } from "./api";
import AnswerContent from "./AnswerContent";
import { ConfirmDialog } from "./ConfirmDialog";
import type { Answer, Source, Question } from "./api";
const statusNames: Record<Answer["status"], string> = {
  answered: "Answer with sources",
  clarification_required: "Needs clarification",
  incomplete: "Incomplete answer",
  evidence_only: "Relevant source excerpts",
  no_evidence: "No matching evidence",
};
export default function App() {
  const [capabilities, setCapabilities] = useState({
    supported_extensions: [".pdf", ".xlsx", ".xlsm"],
    max_upload_bytes: 20 * 1024 * 1024,
  });
  const [sources, setSources] = useState<Source[]>([]);
  const [source, setSource] = useState("");
  const [sheet, setSheet] = useState("");
  const [question, setQuestion] = useState("");
  const [operation, setOperation] = useState("auto");
  const [fields, setFields] = useState<string[]>([]);
  const [filterField, setFilterField] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const [showOperands, setShowOperands] = useState(false);
  const [answeredQuestion, setAnsweredQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState<"upload" | "query" | "remove" | null>(null);
  const [history, setHistory] = useState<
    { question: string; answer: Answer }[]
  >([]);
  const [confirmation, setConfirmation] = useState<Source | "workspace" | null>(
    null,
  );
  const [lastRequest, setLastRequest] = useState<Question | null>(null);
  const revision = useRef(0);
  const session = useRef<string | null>(null);
  // Only a response actually accepted by this UI advances the acknowledged conversation token.
  const context = useRef<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const pending = useRef<AbortController | null>(null);
  const answerRef = useRef<HTMLElement>(null);
  const current = sources.find((s) => s.source_file === source);
  const availableFields = [
    ...new Set(
      current?.sheets
        .filter((s) => !sheet || s.name === sheet)
        .flatMap((s) => s.fields) || [],
    ),
  ].sort();
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api.list(controller.signal),
      api.capabilities(controller.signal),
      api.workspace(),
    ])
      .then(([items, config, state]) => {
        revision.current = state.revision;
        setCapabilities(config);
        setSources(items);
        setSource(items[0]?.source_file || "");
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorMessage(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      controller.abort();
      pending.current?.abort();
    };
  }, []);
  /** Start a fresh local chat/refinement scope; indexed document data is retained. */
  function resetScope(nextSource: string, nextSheet = "") {
    pending.current?.abort();
    pending.current = null;
    setBusy(null);
    if (session.current)
      void api
        .endConversation(session.current)
        .catch(() =>
          setNotice(
            "New chat opened locally; the prior server context will expire automatically.",
          ),
        );
    session.current = null;
    context.current = null;
    setHistory([]);
    setQuestion("");
    setLastRequest(null);
    setSource(nextSource);
    setSheet(nextSheet);
    setFields([]);
    setOperation("auto");
    setFilterField("");
    setFilterValue("");
    setAnswer(null);
    setError("");
  }
  async function refresh() {
    if (busy || loading) return;
    setLoading(true);
    try {
      setError("");
      const [items, config, state] = await Promise.all([
        api.list(),
        api.capabilities(),
        api.workspace(),
      ]);
      revision.current = state.revision;
      setCapabilities(config);
      setSources(items);
      if (!items.some((s) => s.source_file === source))
        resetScope(items[0]?.source_file || "");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }
  /** Validate cheaply in the UI; the server still enforces bytes, type and workspace revision. */
  async function upload(file: File | undefined) {
    if (!file || busy || loading) return;
    if (
      !capabilities.supported_extensions.some((ext) =>
        file.name.toLowerCase().endsWith(ext),
      )
    ) {
      setError(
        `Choose a supported document (${capabilities.supported_extensions.join(", ")}). Re-save legacy XLS files as XLSX.`,
      );
      return;
    }
    if (file.size === 0 || file.size > capabilities.max_upload_bytes) {
      setError(
        `Choose a nonempty file up to ${capabilities.max_upload_bytes / (1024 * 1024)} MB.`,
      );
      return;
    }
    const controller = new AbortController();
    pending.current = controller;
    setBusy("upload");
    setError("");
    setNotice("");
    let uploaded = false;
    try {
      const result = await api.upload(
        file,
        controller.signal,
        revision.current,
      );
      uploaded = true;
      const items = await api.list(controller.signal);
      if (controller.signal.aborted) return;
      setSources(items);
      resetScope(result.source_file);
      setNotice(
        `${result.source_file} indexed · Ready to ask. Processing is automatic.`,
      );
    } catch (e) {
      if (!controller.signal.aborted)
        setError(
          uploaded
            ? `Upload completed, but the document list could not refresh. Use Refresh before retrying the upload. ${errorMessage(e)}`
            : errorMessage(e),
        );
    } finally {
      if (pending.current === controller) {
        pending.current = null;
        setBusy(null);
      }
    }
  }
  /** Send the actual user request and acknowledged context; never inject hidden counting approval. */
  async function query(
    event: React.FormEvent | null,
    text = question,
    options: Partial<Question> = {},
  ) {
    event?.preventDefault();
    if (!text.trim() || !current?.ready || busy || loading) return;
    if (filterField && !filterValue.trim()) {
      setError("Enter a value for the selected equality filter.");
      return;
    }
    const controller = new AbortController();
    pending.current = controller;
    setBusy("query");
    setError("");
    setNotice("");
    try {
      if (!session.current && current?.document_id) {
        const opened = await api.startConversation(
          current,
          revision.current,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        session.current = opened.conversation_id;
      }
      // Explicit choice/page options are one-request overrides, not silently persisted chat settings.
      const payload: Question = {
        operation,
        ...(sheet ? { sheet_or_page: sheet } : {}),
        ...(fields.length ? { fields } : {}),
        ...(filterField ? { filters: { [filterField]: filterValue } } : {}),
        context_token: context.current,
        ...options,
        question: text,
        source_file: source,
        workspace_revision: revision.current,
        ...(current?.document_id ? { document_id: current.document_id } : {}),
        ...(session.current ? { conversation_id: session.current } : {}),
      };
      const result = await api.query(payload, controller.signal);
      if (!controller.signal.aborted) {
        if (!options.page && answer)
          setHistory((previous) =>
            [...previous, { question: answeredQuestion, answer }].slice(-19),
          );
        // A cancelled request cannot publish its answer or context into the current conversation.
        context.current = result.context_token ?? null;
        setLastRequest(payload);
        setAnswer(result);
        setAnsweredQuestion(text);
        if (!options.page)
          setQuestion((value) => (value === text ? "" : value));
        setTimeout(() => answerRef.current?.focus(), 0);
      }
    } catch (e) {
      if (!controller.signal.aborted) setError(errorMessage(e));
    } finally {
      if (pending.current === controller) {
        pending.current = null;
        setBusy(null);
      }
    }
  }
  /** Remove/reset only after confirmation and the server document/revision checks. */
  async function removeData() {
    if (!confirmation) return;
    const selected = confirmation;
    pending.current?.abort();
    pending.current = null;
    setBusy("remove");
    setError("");
    const clear = selected === "workspace" || selected.source_file === source;
    if (clear) {
      setAnswer(null);
      setHistory([]);
      context.current = null;
      session.current = null;
    }
    try {
      const result =
        selected === "workspace"
          ? await api.reset(revision.current)
          : await api.remove(selected);
      revision.current = result.workspace_revision;
      const items = await api.list();
      setSources(items);
      if (clear) resetScope(items[0]?.source_file || "");
      setNotice(
        selected === "workspace"
          ? "Workspace reset. Upload a document to begin."
          : `${selected.source_file} removed from this workspace.`,
      );
    } catch (error) {
      setError(errorMessage(error));
      try {
        const [items, state] = await Promise.all([api.list(), api.workspace()]);
        setSources(items);
        revision.current = state.revision;
      } catch {
        setNotice(
          "Refresh documents before retrying. Cleanup may remain pending.",
        );
      }
    } finally {
      setBusy(null);
      setConfirmation(null);
    }
  }
  function cancel() {
    pending.current?.abort();
    pending.current = null;
    setBusy(null);
    setNotice(
      "Stopped waiting. A request already received by the server may continue; refresh documents before retrying an upload.",
    );
  }
  const referencedNumbers = new Set([
    ...(answer?.answer_items?.flatMap((item) =>
      item.citation_numbers.slice(0, 3),
    ) ?? []),
    ...(answer?.grouped_results?.flatMap((group) => [
      ...group.record_numbers.slice(0, 3),
      ...(group.contributions?.flatMap(
        (contributor) => contributor.record_numbers,
      ) ?? []),
    ]) ?? []),
  ]);
  const visibleCitations = answer
    ? answer.records.length
      ? answer.citations.filter(
          (c) =>
            answer.records.some((r) => r.number === c.number) ||
            referencedNumbers.has(c.number),
        )
      : answer.citations
    : [];
  return (
    <div className="shell">
      <a className="skip-link" href="#question-input">
        Skip to question
      </a>
      <header className="topbar">
        <a className="brand" href="#workspace">
          <span className="brand-icon" aria-hidden="true">
            D.
          </span>
          <span>
            Document Desk<small>RAG MVP · DESKTOP WORKSPACE</small>
          </span>
        </a>
        <span className="local-badge">
          <span />
          Local workspace · 0.3.8
        </span>
        <nav className="header-links" aria-label="Application information">
          <a href="/legal.html" target="_blank" rel="noreferrer">
            License &amp; source
          </a>
          <span>Built with Llama</span>
        </nav>
      </header>
      {confirmation && (
        <ConfirmDialog
          title={
            confirmation === "workspace"
              ? "Reset this workspace?"
              : `Remove ${confirmation.source_file}?`
          }
          description={
            confirmation === "workspace"
              ? `Remove all ${sources.length} indexed documents and associated chat state?`
              : "Remove this document's searchable evidence and chat state? Other documents remain available."
          }
          busy={busy === "remove"}
          onCancel={() => setConfirmation(null)}
          onConfirm={() => void removeData()}
        />
      )}
      <main id="workspace">
        <div className="intro">
          <span className="eyebrow">DOCUMENT INTELLIGENCE · LOCAL MVP</span>
          <h1>Your documents. Clearer answers.</h1>
          <p>
            Ask questions, follow the evidence, and calculate from original
            records.
          </p>
        </div>
        <div className="workspace-grid">
          <aside className="library card">
            <div className="section-title">
              <h2>
                01 <span>Documents</span>
              </h2>
              <button
                className="text-button"
                onClick={() => void refresh()}
                disabled={!!busy}
              >
                Refresh
              </button>
            </div>
            <label
              className={`upload-zone ${busy === "upload" ? "working" : ""}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (e.dataTransfer.files.length !== 1) {
                  setError("Choose one document at a time.");
                  return;
                }
                void upload(e.dataTransfer.files[0]);
              }}
            >
              <span className="upload-symbol" aria-hidden="true">
                ↑
              </span>
              <strong>
                {busy === "upload" ? "Indexing document…" : "Add a document"}
              </strong>
              <span>Drop here or choose a file</span>
              <small>
                {capabilities.supported_extensions.join(", ")} · up to{" "}
                {capabilities.max_upload_bytes / (1024 * 1024)} MB
              </small>
              <input
                aria-label="Upload document"
                type="file"
                accept={capabilities.supported_extensions.join(",")}
                disabled={!!busy || loading}
                onChange={(e) => {
                  void upload(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
            </label>
            <div className="library-caption">
              {loading
                ? "Loading documents…"
                : `${sources.length} indexed document${sources.length === 1 ? "" : "s"}`}
            </div>
            {sources.length === 0 && !loading && (
              <p className="muted">Upload your first document to begin.</p>
            )}
            <ul className="document-list">
              {sources.map((item) => (
                <li key={item.source_file}>
                  <button
                    className={
                      source === item.source_file
                        ? "document active"
                        : "document"
                    }
                    disabled={!!busy}
                    onClick={() => resetScope(item.source_file)}
                  >
                    <span className="file-icon" aria-hidden="true">
                      {item.source_file.split(".").pop()?.toUpperCase()}
                    </span>
                    <span>
                      {item.source_file}
                      <small>
                        {item.ready
                          ? `${item.sheets.length} sheet/page scopes`
                          : item.state === "deleting"
                            ? "Removal pending · retry available"
                            : "Re-index required"}
                      </small>
                    </span>
                    <span aria-hidden="true">↗</span>
                  </button>
                  <button
                    className="text-button danger"
                    type="button"
                    aria-label={`Remove ${item.source_file}`}
                    disabled={busy === "upload" || busy === "remove"}
                    onClick={() => setConfirmation(item)}
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
            <p className="small muted">
              Documents persist across restart. Chat history is session-only and
              clears on reload.
            </p>
            <button
              className="secondary danger"
              type="button"
              disabled={
                !sources.length ||
                loading ||
                busy === "upload" ||
                busy === "remove"
              }
              onClick={() => setConfirmation("workspace")}
            >
              Reset workspace
            </button>
            <p className="library-note">
              Every physical source record is retained. Region continuation
              labels are disclosed in evidence; missing amounts stay unknown.
            </p>
          </aside>
          <section className="question-column">
            <div
              className="workspace-context"
              aria-label="Active document context"
            >
              <div>
                <span className="eyebrow">CURRENT DOCUMENT</span>
                <strong>{source || "Select or upload a document"}</strong>
              </div>
              <span className="context-status">
                {current?.ready ? "Ready to explore" : "Waiting for a document"}
              </span>
            </div>
            <form
              className="card question-card"
              onSubmit={(e) => void query(e)}
            >
              <div className="section-title">
                <h2>
                  02 <span>Ask your document</span>
                </h2>
                <button
                  className="text-button"
                  type="button"
                  disabled={loading || busy === "upload" || busy === "remove"}
                  onClick={() => {
                    resetScope(source);
                    setNotice(
                      "New chat started. Indexed documents were retained.",
                    );
                  }}
                >
                  New chat
                </button>
              </div>
              <div className="scope-grid">
                <label>
                  Document
                  <select
                    aria-label="Document"
                    value={source}
                    disabled={!!busy || !sources.length}
                    onChange={(e) => resetScope(e.target.value)}
                  >
                    <option value="">Choose a document</option>
                    {sources.map((s) => (
                      <option key={s.source_file}>{s.source_file}</option>
                    ))}
                  </select>
                </label>
              </div>
              {current?.warnings?.map((warning) => (
                <p className="notice" key={warning}>
                  {warning}
                </p>
              ))}
              <label className="question-label">
                Your question
                <textarea
                  id="question-input"
                  aria-label="Your question"
                  placeholder={
                    answer
                      ? "Ask a follow-up, such as ‘And South?’"
                      : "What was the Q3 revenue for North?"
                  }
                  value={question}
                  maxLength={4000}
                  rows={3}
                  disabled={
                    busy === "upload" ||
                    busy === "remove" ||
                    current?.ready === false
                  }
                  onChange={(e) => setQuestion(e.target.value)}
                />
              </label>
              <p className="scope-description">
                {sheet ? `Refined to ${sheet}` : "Searching the whole document"}{" "}
                · Compatible cross-sheet questions are supported.
              </p>
              <details className="optional-refinements">
                <summary>Refine sources — optional</summary>
                <label>
                  Sheet or page
                  <select
                    aria-label="Sheet or page"
                    value={sheet}
                    disabled={!!busy || !current}
                    onChange={(e) => resetScope(source, e.target.value)}
                  >
                    <option value="">Entire document</option>
                    {current?.sheets.map((s) => (
                      <option key={s.name}>{s.name}</option>
                    ))}
                  </select>
                </label>
                <details className="scope-options">
                  <summary>Set fields, calculation or equality filter</summary>
                  <p className="muted small">
                    Use these controls when the question needs a precise
                    interpretation. Filters use exact values; blanks are never
                    inferred.
                  </p>
                  <label>
                    Operation
                    <select
                      aria-label="Operation"
                      value={operation}
                      disabled={!!busy}
                      onChange={(e) => setOperation(e.target.value)}
                    >
                      {[
                        ["auto", "Use question wording"],
                        ["lookup", "List matching records"],
                        ["sum", "Sum"],
                        ["minimum", "Minimum"],
                        ["maximum", "Maximum"],
                        ["increase", "Absolute increase"],
                        ["growth_percent", "Percentage growth"],
                      ].map(([v, label]) => (
                        <option value={v} key={v}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <fieldset disabled={!!busy}>
                    <legend>Fields</legend>
                    <div className="field-options">
                      {availableFields.map((f) => (
                        <label key={f}>
                          <input
                            type="checkbox"
                            checked={fields.includes(f)}
                            onChange={(e) =>
                              setFields(
                                e.target.checked
                                  ? [...fields, f]
                                  : fields.filter((x) => x !== f),
                              )
                            }
                          />
                          {f}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                  <div className="scope-grid">
                    <label>
                      Filter field
                      <select
                        aria-label="Filter field"
                        value={filterField}
                        disabled={!!busy}
                        onChange={(e) => setFilterField(e.target.value)}
                      >
                        <option value="">No equality filter</option>
                        {availableFields.map((f) => (
                          <option key={f}>{f}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Equals
                      <input
                        aria-label="Filter value"
                        disabled={!filterField || !!busy}
                        value={filterValue}
                        onChange={(e) => setFilterValue(e.target.value)}
                      />
                    </label>
                  </div>
                  {fields.length === 2 && (
                    <p className="small">
                      Change direction: {fields[0]} → {fields[1]}. Fields follow
                      selection order.
                    </p>
                  )}
                </details>
                <p className="muted small">
                  Processing: {current?.processing_profile?.name || "automatic"}
                  . Manual chunk/index tuning is deferred.
                </p>
              </details>
              <div className="form-footer">
                <span className="muted small">
                  Calculations use all matching indexed rows.
                </span>
                <button
                  className="primary"
                  disabled={
                    !source ||
                    !question.trim() ||
                    !!busy ||
                    current?.ready === false
                  }
                >
                  {busy === "query"
                    ? "Checking source records…"
                    : "Find answer"}{" "}
                  <span aria-hidden="true">↗</span>
                </button>
              </div>
            </form>
            {busy && (
              <div role="status" className="notice">
                {busy === "upload"
                  ? "Parsing, embedding and indexing…"
                  : "Checking your question against the selected document…"}{" "}
                <button
                  className="text-button"
                  disabled={busy === "remove"}
                  onClick={cancel}
                >
                  Stop waiting
                </button>
              </div>
            )}
            {error && (
              <div role="alert" className="notice error">
                {error}
              </div>
            )}
            {notice && (
              <div role="status" className="notice">
                {notice}
              </div>
            )}
            {!!history.length && (
              <section aria-label="Earlier conversation">
                {history.map((turn, index) => (
                  <details
                    className="card history-turn"
                    key={index}
                    id={`turn-${index}-evidence`}
                  >
                    <summary>{turn.question}</summary>
                    <AnswerContent
                      answer={turn.answer}
                      prefix={`turn-${index}-`}
                    />
                    <ol>
                      {turn.answer.citations.map((c) => (
                        <li
                          key={c.number}
                          id={`turn-${index}-citation-${c.number}`}
                          tabIndex={-1}
                        >
                          {c.citation_text}
                        </li>
                      ))}
                    </ol>
                  </details>
                ))}
              </section>
            )}
            {answer ? (
              <section
                className="card answer-card"
                tabIndex={-1}
                ref={answerRef}
                aria-label="Answer"
              >
                <div className="section-title">
                  <h2>
                    03 <span>{statusNames[answer.status]}</span>
                  </h2>
                  <span className={`status-chip ${answer.status}`}>
                    {answer.status.replaceAll("_", " ")}
                  </span>
                </div>
                <div className="answer-layout">
                  <div className="answer-primary">
                    <p className="answered-question">
                      Question:{" "}
                      {answer.resolved_question?.trim() || answeredQuestion}
                    </p>
                    {answer.resolved_question &&
                      answer.resolved_question.trim() !==
                        answeredQuestion.trim() && (
                        <p className="user-message">
                          Your message: {answeredQuestion}
                        </p>
                      )}
                    <AnswerContent answer={answer} />
                    {answer.coverage.returned_records !== undefined && (
                      <p className="coverage">
                        {answer.coverage.returned_records} of{" "}
                        {answer.coverage.matched_records} matching records
                        available in evidence{" "}
                        {answer.coverage.calculation_uses_all_matches && (
                          <>
                            {" "}
                            · Calculation uses all{" "}
                            {answer.coverage.matched_records} matching records
                          </>
                        )}
                        <span>
                          ·{" "}
                          {answer.status === "no_evidence" ||
                          answer.coverage.matched_records === 0
                            ? "No matching source records"
                            : answer.coverage.complete
                              ? "Requested cells present"
                              : "Missing source values"}
                        </span>
                      </p>
                    )}

                    {answer.calculation?.partial && (
                      <p className="coverage subtotal-coverage">
                        Subtotal uses {answer.calculation.operands?.length ?? 0}{" "}
                        of {answer.coverage.matched_records} source records.
                        Missing cells excluded:{" "}
                        {answer.calculation.excluded_cells?.length ?? 0}.
                      </p>
                    )}
                    {answer.coverage.resolved_scopes && (
                      <p className="resolved-scope">
                        Source scope used:{" "}
                        {answer.coverage.resolved_scopes.length
                          ? answer.coverage.resolved_scopes.join(", ")
                          : "Whole document"}
                      </p>
                    )}
                    {!!answer.clarification_options?.length && (
                      <div className="scope-choices">
                        {answer.clarification_options.map((choice) => (
                          <button
                            type="button"
                            className="secondary"
                            key={choice.label}
                            disabled={!!busy}
                            onClick={() => {
                              void query(null, choice.label, {
                                ...(choice.sheet_or_page
                                  ? {
                                      sheet_or_page: choice.sheet_or_page,
                                      source_scopes: [],
                                    }
                                  : {}),
                                ...(choice.aggregation_basis
                                  ? {
                                      aggregation_basis:
                                        choice.aggregation_basis,
                                    }
                                  : {}),
                                ...(choice.record_scope
                                  ? { record_scope: choice.record_scope }
                                  : {}),
                              });
                            }}
                          >
                            {choice.label} →
                          </button>
                        ))}
                      </div>
                    )}
                    {!!answer.unresolved_citation_numbers.length && (
                      <p role="alert" className="error">
                        Unresolved source markers:{" "}
                        {answer.unresolved_citation_numbers.join(", ")}. Treat
                        the answer as unverified.
                      </p>
                    )}
                    {answer.warnings
                      .filter(
                        (w) =>
                          !(
                            answer.calculation?.partial &&
                            w.startsWith("Available-value subtotal:")
                          ),
                      )
                      .map((w) => (
                        <p key={w} className="notice">
                          {w}
                        </p>
                      ))}
                  </div>
                  <aside className="evidence-pane" aria-label="Source evidence">
                    <div className="evidence-heading">
                      <span className="eyebrow">VERIFY THE ANSWER</span>
                      <h3>Source evidence</h3>
                      <p>
                        Original records, cell references and calculation
                        operands.
                      </p>
                    </div>
                    {!!answer.citations.length && (
                      <details
                        className="answer-evidence"
                        id="answer-evidence"
                        key={`${source}-${answeredQuestion}`}
                      >
                        <summary>
                          View evidence ({answer.citations.length} source{" "}
                          {answer.citations.length === 1 ? "record" : "records"}
                          )
                        </summary>
                        {!!answer.records.length && (
                          <div className="table-wrap">
                            <table>
                              <caption>
                                Source records · values and original cell
                                references
                              </caption>
                              <thead>
                                <tr>
                                  <th>Source</th>
                                  {[
                                    ...new Set(
                                      answer.records.flatMap((r) =>
                                        Object.keys(r.values),
                                      ),
                                    ),
                                  ].map((f) => (
                                    <th key={f}>{f}</th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {answer.records.map((r) => (
                                  <tr key={r.number}>
                                    <th scope="row">
                                      <a
                                        href={`#citation-${r.number}`}
                                        onClick={() => {
                                          const details = document
                                            .getElementById(
                                              `citation-${r.number}`,
                                            )
                                            ?.closest("details");
                                          for (
                                            let node: HTMLElement | null =
                                              details ?? null;
                                            node;
                                            node = node.parentElement
                                          ) {
                                            if (
                                              node instanceof HTMLDetailsElement
                                            )
                                              node.open = true;
                                          }
                                        }}
                                      >
                                        [{r.number}] {r.sheet_or_page}
                                      </a>
                                      <small>Row {r.row_or_location}</small>
                                    </th>
                                    {[
                                      ...new Set(
                                        answer.records.flatMap((x) =>
                                          Object.keys(x.values),
                                        ),
                                      ),
                                    ].map((f) => (
                                      <td key={f}>
                                        {r.values[f] ?? (
                                          <em>Missing in source</em>
                                        )}
                                        {r.formula_fields?.[f] && (
                                          <small>
                                            {r.formula_fields[f] ===
                                            "cache_missing"
                                              ? "Formula cache missing"
                                              : "Saved formula value"}
                                          </small>
                                        )}
                                        <small>
                                          {r.cell_references[f] ||
                                            "Table location"}
                                          {r.merged_fields.includes(f)
                                            ? " · merged anchor"
                                            : ""}
                                        </small>
                                        {r.continuation_fields?.[f] && (
                                          <small>
                                            Original cell blank · continued from{" "}
                                            {
                                              r.continuation_fields[f]
                                                .anchor_cell
                                            }{" "}
                                            (row{" "}
                                            {
                                              r.continuation_fields[f]
                                                .anchor_row
                                            }
                                            )
                                          </small>
                                        )}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                        {(answer.coverage.total_pages ?? 1) > 1 && (
                          <nav
                            className="pagination"
                            aria-label="Evidence pages"
                          >
                            <button
                              type="button"
                              disabled={
                                !!busy || (answer.coverage.page ?? 1) <= 1
                              }
                              onClick={() =>
                                void query(
                                  null,
                                  answer.resolved_question || answeredQuestion,
                                  {
                                    ...lastRequest,
                                    context_token: null,
                                    page: (answer.coverage.page ?? 1) - 1,
                                    fields: answer.coverage.fields,
                                  },
                                )
                              }
                            >
                              Previous records
                            </button>
                            <span>
                              Page {answer.coverage.page} of{" "}
                              {answer.coverage.total_pages}
                            </span>
                            <button
                              type="button"
                              disabled={
                                !!busy ||
                                answer.coverage.page ===
                                  answer.coverage.total_pages
                              }
                              onClick={() =>
                                void query(
                                  null,
                                  answer.resolved_question || answeredQuestion,
                                  {
                                    ...lastRequest,
                                    context_token: null,
                                    page: (answer.coverage.page ?? 1) + 1,
                                    fields: answer.coverage.fields,
                                  },
                                )
                              }
                            >
                              Next records
                            </button>
                          </nav>
                        )}
                        {answer.calculation && (
                          <div className="calculation">
                            <span className="eyebrow">
                              {answer.calculation.partial
                                ? "AVAILABLE-VALUE SUBTOTAL"
                                : "CALCULATION"}{" "}
                              ·{" "}
                              {answer.calculation.operation.replaceAll(
                                "_",
                                " ",
                              )}
                            </span>
                            {Object.entries(answer.calculation.result).map(
                              ([field, value]) => (
                                <p key={field}>
                                  <span>
                                    {["increase", "growth_percent"].includes(
                                      answer.calculation?.operation ?? "",
                                    ) &&
                                    answer.records.some(
                                      (r) => String(r.number) === field,
                                    )
                                      ? answer.records
                                          .filter(
                                            (r) => String(r.number) === field,
                                          )
                                          .map((r) => (
                                            <a
                                              key={r.number}
                                              href={`#citation-${r.number}`}
                                            >
                                              {r.sheet_or_page} · row{" "}
                                              {r.row_or_location} · Source [
                                              {r.number}]
                                            </a>
                                          ))
                                      : field}
                                  </span>
                                  <strong>
                                    {value}
                                    {answer.calculation?.unit
                                      ? ` ${answer.calculation.unit}`
                                      : ""}
                                  </strong>
                                </p>
                              ),
                            )}
                          </div>
                        )}
                        {!!answer.calculation?.operands?.length && (
                          <details
                            className="operand-details"
                            onToggle={(event) =>
                              setShowOperands(event.currentTarget.open)
                            }
                          >
                            <summary>
                              Contributing operands (
                              {answer.calculation.operands.length}) · all
                              calculation records
                            </summary>
                            {showOperands && (
                              <ol>
                                {answer.calculation.operands.map((operand) => (
                                  <li key={operand.number}>
                                    <strong>
                                      {operand.source
                                        ? `${operand.source.source_file} / ${operand.source.sheet_or_page} / row ${operand.source.row_or_location}`
                                        : `Source [${operand.number}]`}
                                    </strong>
                                    {Object.entries(operand.values).map(
                                      ([field, value]) => (
                                        <span key={field}>
                                          {" "}
                                          · {field}: {value}
                                          {operand.cell_references?.[field]
                                            ? ` (${operand.cell_references[field]})`
                                            : ""}
                                        </span>
                                      ),
                                    )}
                                  </li>
                                ))}
                              </ol>
                            )}
                          </details>
                        )}
                        {!!answer.citations.length && (
                          <details className="citations">
                            <summary>
                              Source references ({visibleCitations.length}
                              {visibleCitations.length < answer.citations.length
                                ? ` displayed of ${answer.citations.length}`
                                : ""}
                              )
                            </summary>
                            <ol>
                              {visibleCitations.map((c) => (
                                <li
                                  key={c.number}
                                  id={`citation-${c.number}`}
                                  tabIndex={-1}
                                >
                                  <span>[{c.number}]</span> {c.citation_text}
                                </li>
                              ))}
                            </ol>
                          </details>
                        )}
                      </details>
                    )}
                    <details className="diagnostics">
                      <summary>Request details</summary>
                      <p>
                        {answer.resolved_question && (
                          <>Resolved question: {answer.resolved_question}. </>
                        )}
                        Answer path: {answer.execution_path}.{" "}
                        {answer.timings_seconds.total !== undefined
                          ? `Server time: ${answer.timings_seconds.total.toFixed(3)} s.`
                          : ""}{" "}
                        {answer.model
                          ? `Model: ${answer.model}`
                          : "No model-authored values or calculations."}
                      </p>
                    </details>
                  </aside>
                </div>
              </section>
            ) : (
              !busy && (
                <section className="empty-answer">
                  <span className="empty-mark" aria-hidden="true">
                    “
                  </span>
                  <h2>A question is a good place to start.</h2>
                  <p>
                    Choose a document, set the scope if needed, and ask.
                    <br />
                    Your answer and its source records will appear here.
                  </p>
                </section>
              )
            )}
          </section>
        </div>
        <footer>
          Built for traceable answers. Missing evidence is a result worth
          seeing.
        </footer>
      </main>
    </div>
  );
}
