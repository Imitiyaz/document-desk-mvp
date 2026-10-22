/* SPDX-License-Identifier: AGPL-3.0-only */
/**
 * Configure test-setup for this local document assistant.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";
afterEach(() => cleanup());
