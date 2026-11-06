import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';

export default defineConfig(({ mode }) => {
  const ambiente = loadEnv(mode, process.cwd(), 'VITE_');
  const destinoAPI = process.env.VITE_URL_API || ambiente.VITE_URL_API || 'http://localhost:8000';
  return {
    plugins: [react(), tailwindcss()],
    server: {
      proxy: { '^/r/': { target: destinoAPI, changeOrigin: true, followRedirects: false } },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/testes/configuracao.ts'],
      include: ['src/testes/**/*.test.{ts,tsx}'],
    },
  };
});
