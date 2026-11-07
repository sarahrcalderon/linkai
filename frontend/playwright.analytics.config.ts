import { defineConfig } from '@playwright/test';

// Exclusivamente API simulada; não inicia backend nem acessa PostgreSQL.
export default defineConfig({
  testDir: './e2e',
  testMatch: 'analytics.spec.ts',
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:15174',
    browserName: 'chromium',
    trace: 'off',
    channel: process.env.E2E_CANAL || undefined,
  },
  webServer: {
    command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 15174 --strictPort',
    url: 'http://127.0.0.1:15174',
    reuseExistingServer: false,
    env: { VITE_URL_API: 'http://127.0.0.1:18001' },
  },
});
