/* SPDX-License-Identifier: AGPL-3.0-only */
/**
 * Verify ConfirmDialog behavior.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";
afterEach(cleanup);
test("confirmation traps Tab in both directions and returns focus to its trigger", () => {
  const trigger = document.createElement("button");
  document.body.append(trigger);
  trigger.focus();
  const cancel = vi.fn();
  const { unmount } = render(
    <ConfirmDialog
      title="Remove file"
      description="Only this file"
      busy={false}
      onCancel={cancel}
      onConfirm={vi.fn()}
    />,
  );
  const keep = screen.getByRole("button", { name: "Keep data" });
  const confirm = screen.getByRole("button", { name: "Confirm removal" });
  expect(keep).toHaveFocus();
  fireEvent.keyDown(keep, { key: "Tab", shiftKey: true });
  expect(confirm).toHaveFocus();
  fireEvent.keyDown(confirm, { key: "Tab" });
  expect(keep).toHaveFocus();
  fireEvent.keyDown(keep, { key: "Escape" });
  expect(cancel).toHaveBeenCalledOnce();
  unmount();
  expect(trigger).toHaveFocus();
  trigger.remove();
});
test("pending removal keeps keyboard focus inside and cannot be cancelled or duplicated", () => {
  const cancel = vi.fn(),
    confirm = vi.fn();
  const { rerender } = render(
    <ConfirmDialog
      title="Remove file"
      description="Only this file"
      busy={false}
      onCancel={cancel}
      onConfirm={confirm}
    />,
  );
  rerender(
    <ConfirmDialog
      title="Remove file"
      description="Only this file"
      busy={true}
      onCancel={cancel}
      onConfirm={confirm}
    />,
  );
  const dialog = screen.getByRole("alertdialog");
  expect(dialog).toHaveFocus();
  for (const key of ["Escape", "Tab"]) fireEvent.keyDown(dialog, { key });
  expect(dialog).toHaveFocus();
  expect(screen.getByRole("button", { name: "Keep data" })).toBeDisabled();
  expect(
    screen.getByRole("button", { name: "Removing managed data…" }),
  ).toBeDisabled();
  expect(cancel).not.toHaveBeenCalled();
  expect(confirm).not.toHaveBeenCalled();
  rerender(
    <ConfirmDialog
      title="Remove file"
      description="Only this file"
      busy={false}
      onCancel={cancel}
      onConfirm={confirm}
    />,
  );
  expect(screen.getByRole("button", { name: "Keep data" })).toHaveFocus();
});
