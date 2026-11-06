import { test, expect } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const api = 'http://127.0.0.1:18000/api/autenticacao';
const pasta = resolve(
  process.env.E2E_PASTA_EVIDENCIAS || '../docs/relatorios/evidencias/fase4/interface4.4',
);

test('verificação: colagem completa, confirmação e navegação sem sessão automática', async ({
  page,
  context,
}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  let chamadas = 0;
  await page.route(`${api}/verificar-email`, async (rota) => {
    chamadas++;
    expect(Object.keys(rota.request().postDataJSON()).sort()).toEqual(['codigo', 'email']);
    await rota.fulfill({
      status: 200,
      json: { mensagem: 'E-mail verificado. Entre na sua conta para continuar.' },
    });
  });
  await page.goto('/verificar-email');
  await page.getByLabel('E-mail', { exact: true }).fill('pessoa@example.com');
  await page.evaluate(() => navigator.clipboard.writeText('123456'));
  await page.getByLabel('Código de seis dígitos').focus();
  await page.keyboard.press('Control+V');
  expect(await page.getByLabel('Código de seis dígitos').inputValue()).toHaveLength(6);
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', { name: 'Confirmar e-mail' })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('status')).toHaveText(
    'E-mail verificado. Entre na sua conta para continuar.',
  );
  expect(chamadas).toBe(1);
  expect((await context.cookies()).some((cookie) => cookie.name.includes('sessao'))).toBe(false);
  const armazenamento = await page.evaluate(() => ({
    locais: Object.keys(localStorage),
    sessao: Object.keys(sessionStorage),
  }));
  expect(armazenamento.locais.every((chave) => chave === 'tema')).toBe(true);
  expect(armazenamento.sessao).toHaveLength(0);
  await page.getByRole('link', { name: 'Ir para o login' }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test('verificação: reload permite informar e-mail sem dados na URL', async ({ page }) => {
  await page.goto('/verificar-email');
  await page.getByLabel('E-mail', { exact: true }).fill('pessoa@example.com');
  await page.getByLabel('Código de seis dígitos').fill('123456');
  await page.reload();
  await expect(page.getByLabel('E-mail', { exact: true })).toHaveValue('');
  await expect(page.getByLabel('Código de seis dígitos')).toHaveValue('');
  await expect(page).toHaveURL('http://127.0.0.1:15173/verificar-email');
  await page.getByRole('button', { name: 'Confirmar e-mail' }).click();
  await expect(page.getByLabel('E-mail', { exact: true })).toBeFocused();
  await expect(page.getByLabel('Código de seis dígitos')).toHaveAttribute('aria-invalid', 'true');
});

test('verificação: erros neutros, rede, loading, reenvio e cooldown', async ({ page }) => {
  await page.route(`${api}/verificar-email`, (rota) =>
    rota.fulfill({ status: 400, json: { erro: { codigo: 'verificacao_invalida' } } }),
  );
  await page.goto('/verificar-email');
  await page.getByLabel('E-mail', { exact: true }).fill('pessoa@example.com');
  await page.getByLabel('Código de seis dígitos').fill('123456');
  await page.getByRole('button', { name: 'Confirmar e-mail' }).click();
  await expect(page.getByRole('alert')).toContainText('Código inválido ou indisponível.');
  await expect(page.getByLabel('Código de seis dígitos')).toHaveValue('');
  await page.route(`${api}/reenviar-codigo`, (rota) => rota.abort('failed'));
  await page.getByRole('button', { name: 'Reenviar código' }).click();
  await expect(page.getByRole('alert')).toContainText('Não foi possível conectar à API');
  await page.unroute(`${api}/reenviar-codigo`);
  let liberar!: () => void;
  const bloqueio = new Promise<void>((resolver) => {
    liberar = resolver;
  });
  let chamadas = 0;
  await page.route(`${api}/reenviar-codigo`, async (rota) => {
    chamadas++;
    await bloqueio;
    await rota.fulfill({ status: 202, json: { mensagem: 'Solicitação recebida.' } });
  });
  await page.getByRole('button', { name: 'Reenviar código' }).click();
  await expect(page.getByRole('button', { name: 'Solicitando…' })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Confirmar e-mail' })).toBeDisabled();
  liberar();
  await expect(page.getByText(/A entrega pode levar alguns instantes/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reenviar código' })).toBeDisabled();
  expect(chamadas).toBe(1);
});

test('verificação: 375, 768 e 1440 px, temas, contraste e foco', async ({ page, browser }) => {
  mkdirSync(pasta, { recursive: true });
  const medidas = [];
  for (const largura of [375, 768, 1440]) {
    for (const tema of ['claro', 'escuro']) {
      await page.setViewportSize({ width: largura, height: 900 });
      await page.goto('/verificar-email');
      await page.evaluate((tema) => localStorage.setItem('tema', tema), tema);
      await page.reload();
      await expect(page.locator('html')).toHaveAttribute('data-tema', tema);
      const layout = await page.evaluate(() => ({
        semOverflow: document.documentElement.scrollWidth <= window.innerWidth,
        camposLegiveis: Array.from(document.querySelectorAll('input')).every(
          (campo) => parseFloat(getComputedStyle(campo).fontSize) >= 16,
        ),
        alvosAdequados: Array.from(document.querySelectorAll('button, input')).every(
          (alvo) => alvo.getBoundingClientRect().height >= 44,
        ),
      }));
      expect(layout).toEqual({ semOverflow: true, camposLegiveis: true, alvosAdequados: true });
      await page.getByLabel('E-mail', { exact: true }).focus();
      await page.keyboard.press('Tab');
      const campo = page.getByLabel('Código de seis dígitos');
      await expect(campo).toBeFocused();
      expect(
        await campo.evaluate((elemento) => getComputedStyle(elemento).boxShadow !== 'none'),
      ).toBe(true);
      const contrastes = await page.evaluate(() => {
        const tela = document.createElement('canvas');
        tela.width = tela.height = 1;
        const contexto = tela.getContext('2d')!;
        function luminancia(cor: string) {
          contexto.clearRect(0, 0, 1, 1);
          contexto.fillStyle = cor;
          contexto.fillRect(0, 0, 1, 1);
          const valores = [...contexto.getImageData(0, 0, 1, 1).data].slice(0, 3).map((valor) => {
            const v = valor / 255;
            return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
          });
          return valores[0] * 0.2126 + valores[1] * 0.7152 + valores[2] * 0.0722;
        }
        function contraste(frente: string, fundo: string) {
          const a = luminancia(frente),
            b = luminancia(fundo);
          return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        }
        const botao = getComputedStyle(document.querySelector('button[type="submit"]')!);
        const principal = getComputedStyle(document.querySelector('main')!);
        const link = getComputedStyle(document.querySelector('a[href="/login"]')!);
        return {
          botao: contraste(botao.color, botao.backgroundColor),
          texto: contraste(principal.color, principal.backgroundColor),
          link: contraste(link.color, principal.backgroundColor),
        };
      });
      for (const valor of Object.values(contrastes)) expect(valor).toBeGreaterThanOrEqual(4.5);
      medidas.push({ largura, tema, ...layout, contrastes });
      await page.screenshot({
        path: resolve(pasta, `verificacao-${largura}-${tema}.png`),
        fullPage: true,
      });
    }
  }
  writeFileSync(
    resolve(pasta, 'verificacao-layout.json'),
    JSON.stringify({ navegador: browser.version(), medidas }, null, 2) + '\n',
  );
});
