import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests',
  timeout: 45000,
  fullyParallel: false,
  use: {
    baseURL: process.env.DECISIONIQ_TEST_URL || 'http://127.0.0.1:8083',
    channel: 'chrome',
    viewport: { width: 1440, height: 1000 },
    reducedMotion: 'reduce',
    trace: 'retain-on-failure',
  },
  reporter: 'list',
});
