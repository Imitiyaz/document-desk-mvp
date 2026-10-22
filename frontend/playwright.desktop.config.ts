/** Desktop release workflows; historical mobile projects remain available separately.
 * Author: Imitiyaz and AI Agent
 */
import { defineConfig } from "@playwright/test";
import base from "./playwright.config";
export default defineConfig({
  ...base,
  testMatch: "**/desktop.spec.ts",
  testIgnore: [],
  outputDir: "test-results/desktop",
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 1000 } } },
  ],
  reporter: [
    ["list"],
    ["json", { outputFile: "test-results/desktop-results.json" }],
  ],
});
