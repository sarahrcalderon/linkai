import { defineConfig } from '@playwright/test';
import base from './playwright.config';

export default defineConfig({
  ...base,
  testMatch: '**/links-reais.spec.ts',
  testIgnore: [],
  globalSetup: './e2e/preparar-integrado.ts',
  timeout: 120000,
});
