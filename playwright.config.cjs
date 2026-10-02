const { defineConfig } = require("@playwright/test");
module.exports = defineConfig({
  testDir: "tests/frontend",
  use: { headless: true, viewport: { width: 390, height: 1000 } },
  reporter: "list",
});
