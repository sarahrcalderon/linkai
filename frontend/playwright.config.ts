import { defineConfig } from '@playwright/test';
import { resolve } from 'node:path';
import { randomBytes } from 'node:crypto';

const python = process.env.E2E_PYTHON || resolve('../backend/.venv/Scripts/python.exe');
const urlBanco = process.env.URL_BANCO_E2E || '';
let banco: URL;
try {
  banco = new URL(urlBanco || 'postgresql://localhost/nao_configurado');
} catch {
  throw new Error('URL_BANCO_E2E inválida. Use o banco local exclusivo linkai_e2e.');
}
if (!['127.0.0.1', 'localhost'].includes(banco.hostname) || banco.pathname !== '/linkai_e2e') {
  throw new Error('Configure URL_BANCO_E2E para o banco local exclusivo linkai_e2e.');
}

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  testIgnore: '**/links-reais.spec.ts',
  globalSetup: './e2e/preparar.ts',
  workers: 1,
  fullyParallel: false,
  timeout: 45000,
  expect: { timeout: 10000 },
  reporter: [['./e2e/relator.ts']],
  preserveOutput: 'never',
  use: {
    baseURL: 'http://127.0.0.1:15173',
    browserName: 'chromium',
    viewport: { width: 1440, height: 900 },
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn aplicacao.principal:app --host 127.0.0.1 --port 18000 --no-proxy-headers > "../.postgres-teste/e2e-api.log" 2>&1`,
      cwd: '../backend',
      url: 'http://127.0.0.1:18000/api/saude',
      reuseExistingServer: false,
      env: {
        URL_BANCO: urlBanco,
        AMBIENTE: 'teste',
        VERIFICACAO_SEGREDO: randomBytes(32).toString('base64url'),
        OUTBOX_CHAVE: randomBytes(32).toString('base64').replaceAll('+', '-').replaceAll('/', '_'),
        ORIGENS_PERMITIDAS: '["http://127.0.0.1:15173"]',
        CADASTRO_LIMITE_TENTATIVAS: '5',
        CADASTRO_JANELA_SEGUNDOS: '900',
        LOGIN_LIMITE_TENTATIVAS: '10',
        LOGIN_JANELA_SEGUNDOS: '900',
        SESSAO_COOKIE_SEGURO: 'false',
        SESSAO_COOKIE_SAMESITE: 'lax',
      },
      stdout: 'pipe',
      stderr: 'pipe',
    },
    {
      command: 'node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 15173 --strictPort',
      url: 'http://127.0.0.1:15173',
      reuseExistingServer: false,
      env: { VITE_URL_API: 'http://127.0.0.1:18000' },
    },
  ],
});
