import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 180_000,
  use: { baseURL: "http://127.0.0.1:3000", trace: "retain-on-failure", ...devices["Desktop Chrome"] },
  reporter: [["list"], ["html", { outputFolder: "e2e-report", open: "never" }]],
});

