/**
 * Configure local API proxying and isolated component-test execution.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test-setup.ts",
    include: ["src/**/*.test.tsx"],
    coverage: {
      provider: "v8",
      include: [
        "src/App.tsx",
        "src/api.ts",
        "src/ConfirmDialog.tsx",
        "src/AnswerContent.tsx",
      ],
      reporter: ["text", "json-summary"],
    },
  },
});
