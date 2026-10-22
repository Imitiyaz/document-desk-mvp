/* SPDX-License-Identifier: AGPL-3.0-only */
/** Browser capture contracts against the real renderer. Author: Imitiyaz and AI Agent */
import { render } from "@testing-library/react";
import { expect, test } from "vitest";
import AnswerContent from "./AnswerContent";
import { products, absentProduct } from "./test-fixtures/intent";
import { answerTextSelector } from "../e2e/control-names";
import type { Answer } from "./api";
for (const [name, answer, expected] of [
  ["unknown page clarification", { ...absentProduct, status: "clarification_required", answer: "Page 99 is unavailable. Choose page 1 or page 3.", answer_items: [] }, "Page 99 is unavailable"],
  ["tableless page clarification", { ...absentProduct, status: "clarification_required", answer: "Page 2 contains no Quantity table.", answer_items: [] }, "Page 2 contains no Quantity table"],
  ["absent product", absentProduct, "Apple"],
  ["grouped answer", products, "28"],
] as const) {
  test(`browser capture reads ${name} without requiring readable-answer`, () => {
    const { container } = render(<AnswerContent answer={answer as Answer} />);
    const bodies = container.querySelectorAll(answerTextSelector);
    expect(bodies).toHaveLength(1);
    expect(bodies[0]).toHaveTextContent(expected);
    if (name.includes("clarification")) expect(container.querySelector(".readable-answer")).toBeNull();
  });
}
