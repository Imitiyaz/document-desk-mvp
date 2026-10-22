/**
 * Configure playwright config for this local document assistant.
 * Author: Imitiyaz and AI Agent
 * Project: RAG MVP
 */
import { defineConfig, devices } from "@playwright/test";
import { tmpdir } from "node:os";
import { join } from "node:path";
// A fresh isolated index prevents browser checks from deleting or reusing the ordinary workspace.
const verificationDirectory = join(tmpdir(), `rag-browser-${Date.now()}`);
export default defineConfig({
  testDir: "./e2e",
  testIgnore: "**/desktop.spec.ts",
  outputDir: "test-results/e2e",
  fullyParallel: false,
  workers: 1,
  // Do not turn an intermittent conversation failure into an apparently clean release gate.
  retries: 0,
  metadata: { verification_id: verificationDirectory },
  timeout: 45000,
  reporter: [["list"], ["json", { outputFile: "test-results/results.json" }]],
  use: {
    launchOptions: process.env.BROWSER_EXECUTABLE
      ? { executablePath: process.env.BROWSER_EXECUTABLE }
      : {},
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], browserName: "chromium" },
    },
  ],
  webServer: [
    {
      command: `"${process.env.PYTHON_EXECUTABLE || "python"}" -m uvicorn tests.browser_app:app --app-dir ../backend --host 127.0.0.1 --port 8000`,
      url: "http://127.0.0.1:8000/ready",
      reuseExistingServer: false,
      timeout: 60000,
      env: {
        CHROMA_PERSIST_DIR: verificationDirectory,
        UPLOAD_TEMP_DIR: join(verificationDirectory, "uploads"),
      },
    },
    {
      command: "npm run dev -- --port 5173 --strictPort",
      url: "http://127.0.0.1:5173",
      reuseExistingServer: false,
    },
  ],
});
