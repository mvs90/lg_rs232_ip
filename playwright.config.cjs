const { defineConfig } = require("@playwright/test");
module.exports = defineConfig({
  testDir: "tests/frontend",
  use: { headless: true, viewport: { width: 390, height: 1000 } },
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
    { name: "webkit", use: { browserName: "webkit" } },
  ],
  reporter: "list",
});
