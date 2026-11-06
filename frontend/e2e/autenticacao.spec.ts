import { test, expect, type Page } from '@playwright/test';
import { mkdirSync, writeFileSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { operarBanco } from './ambiente';

const api = 'http://127.0.0.1:18000';
const origem = 'http://127.0.0.1:15173';
const pastaEvidencias = resolve('../docs/relatorios/evidencias/fase3');

async function preencher(page: Page, email: string, cadastro = false) {
  if (cadastro) await page.getByLabel('Nome', { exact: true }).fill('Pessoa de teste');
  await page.getByLabel('E-mail', { exact: true }).fill(email);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_SENHA_FIXTURE!);
}

async function entrar(page: Page) {
  await page.goto('/login');
  await preencher(page, 'verificado@example.com');
  const pendente = page.waitForResponse(
    (resposta) => resposta.url().endsWith('/login') && resposta.request().method() === 'POST',
  );
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  const resposta = await pendente;
  expect(resposta.status()).toBe(200);
  const dados = await resposta.json();
  expect(Object.keys(dados).sort()).toEqual(['csrf', 'usuario']);
  expect(Object.keys(dados.usuario).sort()).toEqual(['email', 'email_verificado', 'id', 'nome']);
  expect(JSON.stringify(dados).includes(process.env.E2E_SENHA_FIXTURE!)).toBe(false);
  expect(resposta.headers()['cache-control']).toBe('no-store');
  await expect(page.getByRole('heading', { name: 'Olá, Pessoa de teste.' })).toBeVisible();
}

test('cadastro 202 uniforme, validação e conta não verificada', async ({ page, context }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'Criar conta', exact: true }).click();
  await page.getByRole('button', { name: 'Criar conta', exact: true }).click();
  await expect(page.getByLabel('Nome', { exact: true })).toBeFocused();
  for (const campo of ['Nome', 'E-mail', 'Senha']) {
    await expect(page.getByLabel(campo, { exact: true })).toHaveAttribute('aria-invalid', 'true');
  }
  const mensagens: string[] = [];
  for (let tentativa = 0; tentativa < 2; tentativa++) {
    await preencher(page, 'cadastro@example.com', true);
    const resposta = page.waitForResponse(
      (resposta) => resposta.url().endsWith('/cadastro') && resposta.request().method() === 'POST',
    );
    await page.getByRole('button', { name: 'Criar conta', exact: true }).click();
    const cadastro = await resposta;
    expect(cadastro.status()).toBe(202);
    const dados = await cadastro.json();
    mensagens.push(dados.mensagem);
    expect(Object.keys(dados)).toEqual(['mensagem']);
    await expect(page.getByRole('status')).toHaveText(dados.mensagem);
    await expect(page.getByLabel('Senha', { exact: true })).toHaveValue('');
    expect(
      (await context.cookies(`${api}/api`)).some((cookie) => cookie.name.includes('sessao')),
    ).toBe(false);
  }
  expect(mensagens[0] === mensagens[1]).toBe(true);
  expect(mensagens[0].includes('verificação de e-mail')).toBe(true);
  await page.getByRole('link', { name: 'Entrar', exact: true }).click();
  await preencher(page, 'cadastro@example.com');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('alert')).toHaveText('E-mail ou senha inválidos.');
  await expect(page).toHaveURL(/\/login$/);
});

test('credenciais incorretas e conta inexistente permanecem genéricas', async ({ page }) => {
  await page.goto('/login');
  for (const email of ['verificado@example.com', 'ausente@example.com']) {
    await preencher(page, email);
    await page.getByLabel('Senha', { exact: true }).fill('credencial incorreta de teste');
    await page.getByRole('button', { name: 'Entrar', exact: true }).click();
    await expect(page.getByRole('alert')).toHaveText('E-mail ou senha inválidos.');
    await expect(page).toHaveURL(/\/login$/);
  }
});

test('cookie HttpOnly, CSRF, CORS, reload, logout e revogação reais', async ({ page, context }) => {
  await entrar(page);
  const cookie = (await context.cookies(`${api}/api`)).find(
    (cookie) => cookie.name === 'linkai_sessao',
  );
  expect(Boolean(cookie)).toBe(true);
  expect(cookie!.httpOnly).toBe(true);
  expect(cookie!.sameSite).toBe('Lax');
  expect(cookie!.secure).toBe(false); // Homologação HTTP local, sem reduzir a política de produção.
  expect(cookie!.path).toBe('/api');
  expect(cookie!.domain).toBe('127.0.0.1');
  expect(cookie!.expires > Date.now() / 1000).toBe(true);
  const resumo = await page.evaluate(() => ({
    cookieVisivel: document.cookie.includes('sessao'),
    locais: Object.keys(localStorage),
    sessoes: Object.keys(sessionStorage),
  }));
  expect(resumo.cookieVisivel).toBe(false);
  expect(resumo.locais.every((chave) => chave === 'tema')).toBe(true);
  expect(resumo.sessoes).toHaveLength(0);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Olá, Pessoa de teste.' })).toBeVisible();
  const csrf = await page.evaluate(async (api) => {
    const resposta = await fetch(`${api}/api/autenticacao/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    return resposta.status;
  }, api);
  expect(csrf).toBe(403);
  const preflight = await page.request.fetch(`${api}/api/autenticacao/logout`, {
    method: 'OPTIONS',
    headers: { Origin: 'https://origem-invalida.example', 'Access-Control-Request-Method': 'POST' },
  });
  expect(preflight.status()).toBe(400);
  expect(Boolean(preflight.headers()['access-control-allow-origin'])).toBe(false);
  const outraOrigem = await context.newPage();
  await outraOrigem.goto('data:text/html,<title>Origem isolada</title>');
  const bloqueada = await outraOrigem.evaluate(async (api) => {
    try {
      await fetch(`${api}/api/saude`, { credentials: 'include' });
      return false;
    } catch {
      return true;
    }
  }, api);
  expect(bloqueada).toBe(true);
  await outraOrigem.close();
  const respostaLogout = page.waitForResponse(
    (resposta) =>
      resposta.url().endsWith('/logout') &&
      resposta.request().method() === 'POST' &&
      resposta.status() === 204,
  );
  await page.getByRole('button', { name: 'Sair', exact: true }).click();
  const logout = await respostaLogout;
  expect(Boolean(logout.request().headers()['x-csrf-token'])).toBe(true);
  await expect(page).toHaveURL(/\/login$/);
  expect(
    (await context.cookies(`${api}/api`)).some((cookie) => cookie.name === 'linkai_sessao'),
  ).toBe(false);
  // Mantém o token só na memória do teste para comprovar que o servidor rejeita replay.
  await context.addCookies([cookie!]);
  const replay = await page.request.get(`${api}/api/usuarios/me`);
  expect(replay.status()).toBe(401);
});

test('rota privada sem autenticação e histórico de navegação', async ({ page }) => {
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText('Sua conta está conectada ao Linkai.')).toHaveCount(0);
  await page.getByRole('link', { name: 'Criar conta', exact: true }).click();
  await expect(page).toHaveURL(/\/cadastro$/);
  await page.goBack();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByRole('link', { name: 'Linkai, início' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Conecte pessoas');
});

test('sessão expirada no PostgreSQL remove acesso', async ({ page }) => {
  await entrar(page);
  operarBanco('expirar');
  await page.getByRole('button', { name: 'Atualizar sessão' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole('alert')).toHaveText('Sua sessão expirou. Entre novamente.');
});

test('falha de conexão e indisponibilidade real do banco falham com segurança', async ({
  page,
}) => {
  await page.route(`${api}/**`, (rota) => rota.abort('connectionrefused'));
  await page.goto('/dashboard');
  await expect(page.getByRole('alert')).toContainText('Não foi possível conectar à API');
  await expect(page.getByText('Sua conta está conectada ao Linkai.')).toHaveCount(0);
  await page.unroute(`${api}/**`);
  await page.getByRole('button', { name: 'Tentar novamente' }).click();
  await expect(page).toHaveURL(/\/login$/);
  await entrar(page);
  operarBanco('suspender');
  try {
    await page.getByRole('button', { name: 'Atualizar sessão' }).click();
    await expect(page.getByRole('alert')).toContainText('O serviço está indisponível');
    await expect(page.getByText('Sua conta está conectada ao Linkai.')).toHaveCount(0);
  } finally {
    operarBanco('restaurar');
  }
  await page.getByRole('button', { name: 'Tentar novamente' }).click();
  await expect(page.getByRole('heading', { name: 'Olá, Pessoa de teste.' })).toBeVisible();
});

async function verificarLayout(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  );
  const controles = page.locator('input, button');
  for (const controle of await controles.all()) {
    if (!(await controle.isVisible())) continue;
    const caixa = await controle.boundingBox();
    expect(
      Boolean(
        caixa &&
        caixa.height >= 44 &&
        caixa.x >= 0 &&
        caixa.x + caixa.width <= page.viewportSize()!.width,
      ),
    ).toBe(true);
  }
  expect(
    await page
      .locator('input')
      .evaluateAll((campos) =>
        campos.every((campo) => parseFloat(getComputedStyle(campo).fontSize) >= 16),
      ),
  ).toBe(true);
}

test('375, 768 e 1440 px, temas, foco, teclado e evidências visuais', async ({ page, browser }) => {
  mkdirSync(pastaEvidencias, { recursive: true });
  writeFileSync(
    resolve(pastaEvidencias, 'ambiente-navegador.json'),
    JSON.stringify(
      {
        navegador: 'Chromium',
        versao: browser.version(),
        plataforma: process.platform,
        larguras: [375, 768, 1440],
        altura: 900,
        temas: ['claro', 'escuro'],
      },
      null,
      2,
    ) + '\n',
  );
  const medidas: { largura: number; tema: string; contrasteBotao: number }[] = [];
  for (const largura of [375, 768, 1440]) {
    await page.setViewportSize({ width: largura, height: 900 });
    for (const tema of ['claro', 'escuro']) {
      await page.goto('/cadastro');
      await page.evaluate((tema) => localStorage.setItem('tema', tema), tema);
      await page.reload();
      await expect(page.locator('html')).toHaveAttribute('data-tema', tema);
      for (const caminho of ['/cadastro', '/login']) {
        await page.goto(caminho);
        await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
        await verificarLayout(page);
        await page.screenshot({
          path: resolve(pastaEvidencias, `${caminho.slice(1)}-${largura}-${tema}.png`),
          fullPage: true,
        });
      }
      await page.getByLabel('E-mail', { exact: true }).focus();
      await page.keyboard.press('Tab');
      await expect(page.getByLabel('Senha', { exact: true })).toBeFocused();
      expect(
        await page.getByLabel('Senha', { exact: true }).evaluate((campo) => {
          const estilo = getComputedStyle(campo);
          return (
            estilo.boxShadow !== 'none' ||
            (estilo.outlineStyle !== 'none' && estilo.outlineWidth !== '0px')
          );
        }),
      ).toBe(true);
      const contraste = await page
        .getByRole('button', { name: 'Entrar', exact: true })
        .evaluate((botao) => {
          const tela = document.createElement('canvas');
          tela.width = tela.height = 1;
          const contexto = tela.getContext('2d')!;
          function luminancia(cor: string) {
            contexto.clearRect(0, 0, 1, 1);
            contexto.fillStyle = cor;
            contexto.fillRect(0, 0, 1, 1);
            const valores = Array.from(contexto.getImageData(0, 0, 1, 1).data)
              .slice(0, 3)
              .map((v) => {
                const canal = v / 255;
                return canal <= 0.04045 ? canal / 12.92 : ((canal + 0.055) / 1.055) ** 2.4;
              });
            return valores[0] * 0.2126 + valores[1] * 0.7152 + valores[2] * 0.0722;
          }
          const estilo = getComputedStyle(botao);
          const frente = luminancia(estilo.color),
            fundo = luminancia(estilo.backgroundColor);
          return (Math.max(frente, fundo) + 0.05) / (Math.min(frente, fundo) + 0.05);
        });
      expect(contraste).toBeGreaterThanOrEqual(4.5);
      medidas.push({ largura, tema, contrasteBotao: contraste });
    }
  }
  await entrar(page);
  for (const largura of [375, 768, 1440]) {
    await page.setViewportSize({ width: largura, height: 900 });
    for (const tema of ['claro', 'escuro']) {
      const temaAtual = await page.locator('html').getAttribute('data-tema');
      if (temaAtual !== tema)
        await page
          .getByRole('button', {
            name: tema === 'claro' ? 'Ativar tema claro' : 'Ativar tema escuro',
          })
          .click();
      await verificarLayout(page);
      await page.screenshot({
        path: resolve(pastaEvidencias, `conta-${largura}-${tema}.png`),
        fullPage: true,
        mask: [page.getByText('verificado@example.com')],
      });
    }
  }
  writeFileSync(
    resolve(pastaEvidencias, 'medidas-layout.json'),
    JSON.stringify(medidas, null, 2) + '\n',
  );
});

test('loading real e bloqueio de múltiplos envios', async ({ page }) => {
  let liberar!: () => void;
  const bloqueio = new Promise<void>((resolver) => {
    liberar = resolver;
  });
  await page.route(`${api}/api/autenticacao/login`, async (rota) => {
    await bloqueio;
    await rota.continue();
  });
  await page.goto('/login');
  await preencher(page, 'verificado@example.com');
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Enviando…' })).toBeDisabled();
  await expect(page.getByLabel('E-mail', { exact: true })).toBeDisabled();
  liberar();
  await expect(page.getByRole('heading', { name: 'Olá, Pessoa de teste.' })).toBeVisible();
});

test('limite de tentativas permanece ativo', async ({ page }) => {
  await page.goto('/login');
  const status = await page.evaluate(
    async ({ api }) => {
      let ultimo = 0;
      for (let tentativa = 0; tentativa < 11; tentativa++) {
        const resposta = await fetch(`${api}/api/autenticacao/login`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: '{}',
        });
        ultimo = resposta.status;
      }
      return ultimo;
    },
    { api, origem },
  );
  expect(status).toBe(429);
});

test('logs da API não registram credenciais ou tokens', async () => {
  const registros = readFileSync(resolve('../.postgres-teste/e2e-api.log'), 'utf-8');
  expect(registros.includes(process.env.E2E_SENHA_FIXTURE!)).toBe(false);
  expect(registros.includes(process.env.URL_BANCO_E2E!)).toBe(false);
  expect(/(?:__Host-)?linkai_sessao=[A-Za-z0-9_-]+/.test(registros)).toBe(false);
  expect(/\b[a-f0-9]{64}\b/.test(registros)).toBe(false);
});
