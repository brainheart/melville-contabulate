const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 30000,
  retries: 0,
  use: {
    baseURL: 'http://localhost:8767',
    headless: true,
  },
  webServer: {
    command: 'python3 -m http.server 8767 -d docs',
    port: 8767,
    reuseExistingServer: true,
  },
});
