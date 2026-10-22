/** Accessible-name contract exercised by the rendered App and Playwright.
 * Author: Imitiyaz and AI Agent
 */
export const sourceRecordsButtonName = "Use source records \u2192";

// Shared with rendered-DOM regressions; clarification text is intentionally plain.
export const answerTextSelector = ".answer-text, .readable-answer";
export const documentLibraryReadyText = /^\d+ indexed documents?$/;

// Exercised against the rendered reset confirmation before browser selectors use them.
export const confirmationDialogRole = "alertdialog" as const;
export const keepDataButtonName = "Keep data";
