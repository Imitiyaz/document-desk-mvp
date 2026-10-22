/* SPDX-License-Identifier: AGPL-3.0-only */
/**
 * Define the browser API contract and map transport failures into readable messages.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import axios from "axios";
export interface Source {
  document_id?: string;
  workspace_revision?: number;
  state?: string;
  processing_profile?: { name?: string };
  warnings?: string[];
  source_file: string;
  ready: boolean;
  sha256: string;
  sheets: { name: string; fields: string[] }[];
}
export interface Citation {
  number: number;
  source_file: string;
  sheet_or_page: string;
  row_or_location: string | number;
  citation_text: string;
}
/** Physical source records; null values, raw blanks and continuation provenance remain explicit. */
export interface Evidence {
  number: number;
  source_file: string;
  sheet_or_page: string;
  row_or_location: string | number;
  values: Record<string, string | null>;
  cell_references: Record<string, string>;
  merged_fields: string[];
  cell_formats?: Record<string, string>;
  formula_fields?: Record<string, string>;
  continuation_fields?: Record<
    string,
    {
      value: string;
      original_value: string | null;
      original_cell: string;
      anchor_cell: string;
      anchor_row: number;
      policy: string;
    }
  >;
}
export interface AnswerItem {
  kind: "paragraph" | "record" | "calculation" | "notice";
  text: string;
  citation_numbers: number[];
  record_number?: number | null;
  scope?: string | null;
}
/** Results and their completeness are separate: an exact subtotal can still be incomplete. */
export interface Answer {
  context_token?: string | null;
  document_id?: string | null;
  conversation_id?: string | null;
  workspace_revision?: number;
  resolved_question?: string;
  clarification_options?: {
    label: string;
    field?: string;
    sheet_or_page?: string;
    record_scope?: "detail" | "summary";
    aggregation_basis?: "all_selected_records";
  }[];
  status:
    | "answered"
    | "clarification_required"
    | "incomplete"
    | "evidence_only"
    | "no_evidence";
  execution_path: string;
  answer: string;
  answer_items?: AnswerItem[];
  evidence_text?: string | null;
  records: Evidence[];
  citations: Citation[];
  unresolved_citation_numbers: number[];
  coverage: {
    group_field?: string;
    population_basis?: string;
    fields?: string[];
    resolved_scopes?: string[];
    page?: number;
    total_pages?: number;
    calculation_uses_all_matches?: boolean;
    complete?: boolean;
    matched_records?: number;
    returned_records?: number;
    available_scopes?: string[];
  };
  calculation: {
    operation: string;
    partial?: boolean;
    excluded_cells?: {
      number: number;
      field: string;
      cell: string | null;
      reason: string;
      source: {
        source_file: string;
        sheet_or_page: string;
        row_or_location: string | number;
      };
    }[];
    operands?: {
      number: number;
      values: Record<string, string>;
      cell_references?: Record<string, string>;
      source?: {
        source_file: string;
        sheet_or_page: string;
        row_or_location: string | number;
      };
    }[];
    result: Record<string, string>;
    unit: string;
  } | null;
  grouped_results?: {
    label: string;
    scope: string;
    entities: string[];
    status: string;
    answer: string;
    record_numbers: number[];
    missing_entities: string[];
    calculation: Answer["calculation"];
    contributions?: {
      entity: string | null;
      status: string;
      record_numbers: number[];
      calculation: Answer["calculation"];
      missing_cells: { number: number; field: string; cell: string | null }[];
    }[];
  }[];
  warnings: string[];
  timings_seconds: Record<string, number>;
  model: string | null;
}
/** Context tokens acknowledge visible responses; omit a counting choice unless the user supplied it. */
export interface Question {
  context_token?: string | null;
  conversation_id?: string;
  document_id?: string;
  workspace_revision?: number;
  source_scopes?: string[];
  record_scope?: "auto" | "detail" | "summary";
  aggregation_basis?: "auto" | "all_selected_records";
  page?: number;
  page_size?: number;
  question: string;
  source_file: string;
  sheet_or_page?: string;
  fields?: string[];
  filters?: Record<string, string>;
  operation: string;
}
// Same-origin /api supports the Vite proxy; deployments may configure a separate API base URL.
const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api",
  timeout: 180000,
});
export const api = {
  workspace: async () =>
    (await client.get<{ revision: number }>("/workspace")).data,
  startConversation: async (
    source: Source,
    revision: number,
    signal?: AbortSignal,
  ) =>
    (
      await client.post<{ conversation_id: string }>(
        "/conversations",
        {
          source_file: source.source_file,
          document_id: source.document_id,
          workspace_revision: revision,
        },
        { signal },
      )
    ).data,
  endConversation: async (id: string) =>
    (await client.delete(`/conversations/${encodeURIComponent(id)}`)).data,
  remove: async (source: Source) =>
    (
      await client.delete<{ workspace_revision: number }>(
        `/documents/${encodeURIComponent(source.source_file)}`,
        { params: { document_id: source.document_id } },
      )
    ).data,
  reset: async (revision: number) =>
    (
      await client.delete<{ workspace_revision: number }>("/workspace", {
        params: { revision },
      })
    ).data,
  capabilities: async (signal?: AbortSignal) =>
    (
      await client.get<{
        supported_extensions: string[];
        max_upload_bytes: number;
      }>("/capabilities", { signal })
    ).data,
  list: async (signal?: AbortSignal) =>
    (await client.get<Source[]>("/documents", { signal })).data,
  upload: async (file: File, signal?: AbortSignal, revision?: number) => {
    const form = new FormData();
    form.append("file", file);
    return (
      await client.post<{ source_file: string; chunks_stored: number }>(
        "/documents",
        form,
        {
          signal,
          ...(revision !== undefined
            ? { headers: { "X-Workspace-Revision": String(revision) } }
            : {}),
        },
      )
    ).data;
  },
  query: async (question: Question, signal?: AbortSignal) =>
    (await client.post<Answer>("/query", question, { signal })).data,
};
export function errorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as
      { message?: string; status_code?: number; code?: string } | undefined;
    if (data?.message)
      return `${data.message} (HTTP ${error.response?.status}${data.code ? ` · ${data.code}` : ""})`;
    if (error.code === "ECONNABORTED")
      return "The request timed out. The server may still be processing it; refresh the document list before retrying an upload.";
    return "Could not reach the API. Check that the backend is running, then try again.";
  }
  return error instanceof Error
    ? error.message
    : "The request could not be completed.";
}
