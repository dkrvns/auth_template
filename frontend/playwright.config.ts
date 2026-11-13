import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  retries: 0,
  timeout: 30_000,
  reporter: 'line',
  outputDir: '/tmp/frontend-test-results',
  use: {
    baseURL: process.env.FRONTEND_BASE_URL ?? 'http://frontend:8080',
    browserName: 'chromium',
    viewport: { width: 1366, height: 900 },
    screenshot: 'only-on-failure',
    trace: 'off',
  },
});
