/* SPDX-License-Identifier: AGPL-3.0-only */
/**
 * Confirm destructive actions with deliberate focus and keyboard handling.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import { useEffect, useRef } from "react";
export function ConfirmDialog({
  title,
  description,
  busy,
  onCancel,
  onConfirm,
}: {
  title: string;
  description: string;
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const panel = useRef<HTMLDivElement>(null),
    cancel = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    // Make keeping data the initial action and restore the previous focus when the dialog closes.
    cancel.current?.focus();
    return () => previous?.focus();
  }, []);
  useEffect(() => {
    if (busy) panel.current?.focus();
    else if (document.activeElement === panel.current) cancel.current?.focus();
  }, [busy]);
  return (
    <div className="modal-backdrop">
      <div
        className="card confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        aria-describedby="confirm-description"
        ref={panel}
        tabIndex={-1}
        onKeyDown={(event) => {
          if (event.key === "Escape" && !busy) {
            event.preventDefault();
            onCancel();
          }
          if (event.key === "Tab") {
            const buttons = [
              ...(panel.current?.querySelectorAll<HTMLButtonElement>(
                "button:not(:disabled)",
              ) ?? []),
            ];
            if (buttons.length === 0) {
              event.preventDefault();
              panel.current?.focus();
              return;
            }
            const first = buttons[0],
              last = buttons.at(-1);
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last?.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first?.focus();
            }
          }
        }}
      >
        <h2 id="confirm-title">{title}</h2>
        <p id="confirm-description">{description}</p>
        <div className="dialog-actions">
          <button type="button" ref={cancel} disabled={busy} onClick={onCancel}>
            Keep data
          </button>
          <button
            className="secondary danger"
            type="button"
            disabled={busy}
            onClick={onConfirm}
          >
            {busy ? "Removing managed data…" : "Confirm removal"}
          </button>
        </div>
      </div>
    </div>
  );
}
