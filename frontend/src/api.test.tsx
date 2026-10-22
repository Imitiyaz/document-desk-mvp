/* SPDX-License-Identifier: AGPL-3.0-only */
/**
 * Verify api behavior.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import { expect, test, vi, beforeEach } from "vitest";
const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  delete: vi.fn(),
}));
vi.mock("axios", async (original) => {
  const real = await original<typeof import("axios")>();
  return { ...real, default: { ...real.default, create: () => mocks } };
});
import { api, errorMessage } from "./api";
import { AxiosError } from "axios";
beforeEach(() => {
  vi.resetAllMocks();
});
test("list passes abort signal and returns data", async () => {
  const c = new AbortController();
  mocks.get.mockResolvedValue({ data: [{ source_file: "a.xlsx" }] });
  expect(await api.list(c.signal)).toEqual([{ source_file: "a.xlsx" }]);
  expect(mocks.get).toHaveBeenCalledWith("/documents", { signal: c.signal });
});
test("upload sends FormData without manually overriding multipart boundary", async () => {
  const file = new File(["data"], "a.pdf");
  mocks.post.mockResolvedValue({
    data: { source_file: "a.pdf", chunks_stored: 1 },
  });
  await api.upload(file);
  const [path, form] = mocks.post.mock.calls[0];
  expect(path).toBe("/documents");
  expect((form as FormData).get("file")).toBe(file);
});
test("query preserves exact source/scope/fields/filters", async () => {
  const data = {
    question: "Q3?",
    source_file: "x.xlsx",
    sheet_or_page: "Sheet",
    fields: ["Q3"],
    filters: { Region: "North" },
    operation: "sum",
  };
  mocks.post.mockResolvedValue({ data: { answer: "169000" } });
  expect(await api.query(data)).toEqual({ answer: "169000" });
  expect(mocks.post.mock.calls[0][1]).toEqual(data);
});
test("HTTP error includes actual status and stable code", () => {
  const e = new AxiosError("bad");
  e.response = {
    status: 409,
    data: { message: "Duplicate", code: "document_exists" },
    statusText: "Conflict",
    headers: {},
    config: {} as never,
  };
  expect(errorMessage(e)).toBe("Duplicate (HTTP 409 · document_exists)");
});
test("timeout warns about unknown server completion; network and unknown errors remain understandable", () => {
  expect(errorMessage(new AxiosError("timeout", "ECONNABORTED"))).toContain(
    "may still be processing",
  );
  expect(errorMessage(new AxiosError("network"))).toContain(
    "backend is running",
  );
  expect(errorMessage("unknown")).toBe("The request could not be completed.");
});

test("capabilities reads current server formats and budget", async () => {
  mocks.get.mockResolvedValue({
    data: { supported_extensions: [".future"], max_upload_bytes: 1000 },
  });
  expect(await api.capabilities()).toEqual({
    supported_extensions: [".future"],
    max_upload_bytes: 1000,
  });
  expect(mocks.get).toHaveBeenCalledWith("/capabilities", {
    signal: undefined,
  });
});

test("lifecycle requests carry document identity and workspace revision", async () => {
  mocks.get.mockResolvedValue({ data: { revision: 2 } });
  expect(await api.workspace()).toEqual({ revision: 2 });
  const source = {
    source_file: "Budget #1.xlsx",
    document_id: "doc-1",
    ready: true,
    sha256: "x",
    sheets: [],
  };
  mocks.post.mockResolvedValue({ data: { conversation_id: "chat-1" } });
  await api.startConversation(source, 2);
  expect(mocks.post).toHaveBeenCalledWith(
    "/conversations",
    {
      source_file: source.source_file,
      document_id: "doc-1",
      workspace_revision: 2,
    },
    { signal: undefined },
  );
  mocks.delete.mockResolvedValue({ data: { workspace_revision: 3 } });
  await api.remove(source);
  expect(mocks.delete).toHaveBeenCalledWith("/documents/Budget%20%231.xlsx", {
    params: { document_id: "doc-1" },
  });
  await api.reset(3);
  expect(mocks.delete).toHaveBeenCalledWith("/workspace", {
    params: { revision: 3 },
  });
  await api.endConversation("chat-1");
  expect(mocks.delete).toHaveBeenCalledWith("/conversations/chat-1");
});
