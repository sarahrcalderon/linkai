import { test, expect, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { resolve } from 'node:path';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { operarBanco } from './ambiente';

const api = 'http://127.0.0.1:18000';
const origem = 'http://127.0.0.1:15173';
const pasta = resolve(
  process.env.E2E_PASTA_EVIDENCIAS || '../docs/relatorios/evidencias/fase5/integrada5.5',
);
function consultarBanco(entrada: object) {
  return JSON.parse(
    execFileSync(
      process.env.E2E_PYTHON || resolve('../backend/.venv/Scripts/python.exe'),
      ['-m', 'testes.e2e.consultar_link'],
      {
        cwd: resolve('../backend'),
        env: { ...process.env, PYTHONPATH: 'src', PYTHONUTF8: '1' },
        input: JSON.stringify(entrada),
        encoding: 'utf8',
        stdio: ['pipe', 'pipe', 'pipe'],
      },
    ),
  );
}
function conferir(id: string, esperado: object) {
  expect(consultarBanco({ id, esperado })).toEqual({
    encontrado: true,
    campos_correspondem: true,
    exclusao_corresponde: true,
  });
}
async function entrar(page: Page, email = 'verificado@example.com') {
  await page.goto('/login');
  await page.getByLabel('E-mail', { exact: true }).fill(email);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_SENHA_FIXTURE!);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Meus links' })).toBeVisible();
  await expect(page.getByText('Carregando links…')).toHaveCount(0);
}
async function csrf(page: Page) {
  const resposta = await page.request.get(api + '/api/usuarios/me');
  expect(resposta.status()).toBe(200);
  return (await resposta.json()).csrf as string;
}
async function escrever(page: Page, metodo: string, caminho: string, dados?: object) {
  return page.request.fetch(api + caminho, {
    method: metodo,
    headers: { Origin: origem, 'X-CSRF-Token': await csrf(page) },
    ...(dados ? { data: dados } : {}),
  });
}
const dados = (slug: string) => ({
  nome: 'Link de teste',
  slug,
  numero_whatsapp: '+5511999999999',
  mensagem: 'Olá 👋\nQuero saber mais & conversar.',
});
async function publico(page: Page, slug: string, status: number, mensagem?: string | null) {
  const resposta = await page.request.get(origem + '/r/' + slug, { maxRedirects: 0 });
  expect(resposta.status()).toBe(status);
  expect(resposta.headers()['cache-control']).toContain('no-store');
  expect(Boolean(resposta.headers()['set-cookie'])).toBe(false);
  if (status === 302) {
    const url = new URL(resposta.headers().location);
    expect(url.protocol === 'https:' && url.hostname === 'wa.me').toBe(true);
    expect(url.searchParams.get('text') === mensagem).toBe(true);
  } else {
    expect(Boolean(resposta.headers().location)).toBe(false);
  }
}

test.beforeEach(async ({ context }) => {
  operarBanco('preparar');
  // Apenas uma guarda: nenhuma resposta de API é simulada nesta suíte.
  await context.route('**/*', (rota) => {
    const url = new URL(rota.request().url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) {
      throw new Error('Requisição externa bloqueada no teste integrado.');
    }
    return rota.continue();
  });
});

test('integrado real: login, CRUD, PostgreSQL, clipboard e redirecionamento sem seguir destino', async ({
  page,
  context,
}) => {
  expect(consultarBanco({ operacao: 'metadados' })).toEqual({
    postgresql: '18.6',
    revisao: '0006',
  });
  await entrar(page);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Meus links' })).toBeVisible();
  const cookie = (await context.cookies(api + '/api')).find((c) => c.name === 'linkai_sessao');
  expect(Boolean(cookie?.httpOnly && cookie.sameSite === 'Lax' && cookie.path === '/api')).toBe(
    true,
  );
  expect(await page.evaluate(() => document.cookie.includes('linkai_sessao'))).toBe(false);
  await page.getByRole('button', { name: 'Criar link', exact: true }).click();
  const form = page.getByRole('dialog', { name: 'Criar link' });
  await form.getByLabel('Nome interno').fill('Link integrado');
  await form.getByLabel('Slug personalizado').fill('integrado-crud');
  await form.getByLabel('Número de WhatsApp').fill('+55 (11) 99999-9999');
  const mensagem = 'Olá 👋\nQuero saber mais & conversar.';
  await form.getByLabel('Mensagem predefinida (opcional)').fill(mensagem);
  const criado = page.waitForResponse(
    (r) => r.url() === api + '/api/links' && r.request().method() === 'POST',
  );
  await form.getByRole('button', { name: 'Salvar link' }).click();
  const resposta = await criado;
  expect(resposta.status()).toBe(201);
  const link = await resposta.json();
  await expect(page.getByRole('heading', { name: 'Link integrado', exact: true })).toBeVisible();
  conferir(link.id, {
    nome: 'Link integrado',
    slug: 'integrado-crud',
    numero_whatsapp: '+5511999999999',
    mensagem,
    ativo: true,
    excluido: false,
  });
  await publico(page, 'integrado-crud', 302, mensagem);
  const visitante = await context.browser()!.newContext();
  try {
    const r = await visitante.request.get(origem + '/r/integrado-crud', { maxRedirects: 0 });
    expect(r.status()).toBe(302);
    expect(new URL(r.headers().location).hostname).toBe('wa.me');
  } finally {
    await visitante.close();
  }
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await page.getByRole('button', { name: 'Copiar URL de Link integrado' }).click();
  await expect(page.getByText('URL copiada.', { exact: true })).toBeVisible();
  expect(new URL(await page.evaluate(() => navigator.clipboard.readText())).pathname).toBe(
    '/r/integrado-crud',
  );
  await page.getByRole('button', { name: 'Criar link', exact: true }).click();
  const duplicado = page.getByRole('dialog', { name: 'Criar link' });
  await duplicado.getByLabel('Nome interno').fill('Duplicado');
  await duplicado.getByLabel('Slug personalizado').fill('integrado-crud');
  await duplicado.getByLabel('Número de WhatsApp').fill('+5511999999999');
  await duplicado.getByRole('button', { name: 'Salvar link' }).click();
  await expect(duplicado.getByLabel('Slug personalizado')).toHaveAttribute('aria-invalid', 'true');
  await duplicado.getByRole('button', { name: 'Cancelar' }).click();
  await duplicado.getByRole('button', { name: 'Descartar alterações' }).click();
  await page.getByRole('button', { name: 'Editar', exact: true }).click();
  const editar = page.getByRole('dialog', { name: 'Editar link' });
  await editar.getByLabel('Nome interno').fill('Link atualizado');
  await editar.getByLabel('Slug personalizado').fill('integrado-novo');
  await editar.getByLabel('Número de WhatsApp').fill('+441234567890');
  await editar.getByLabel('Mensagem predefinida (opcional)').fill('Nova mensagem 🚀');
  await editar.getByRole('button', { name: 'Salvar link' }).click();
  await expect(page.getByText('Link atualizado.', { exact: true })).toBeVisible();
  conferir(link.id, {
    nome: 'Link atualizado',
    slug: 'integrado-novo',
    numero_whatsapp: '+441234567890',
    mensagem: 'Nova mensagem 🚀',
  });
  await publico(page, 'integrado-crud', 404);
  await publico(page, 'integrado-novo', 302, 'Nova mensagem 🚀');
  await page.getByRole('button', { name: 'Editar', exact: true }).click();
  await page.getByLabel('Mensagem predefinida (opcional)').fill('');
  await page.getByRole('button', { name: 'Salvar link' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  conferir(link.id, { mensagem: null });
  await publico(page, 'integrado-novo', 302, null);
  await page.getByRole('button', { name: 'Desativar', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Ativar', exact: true })).toBeVisible();
  conferir(link.id, { ativo: false });
  await publico(page, 'integrado-novo', 404);
  await page.getByRole('button', { name: 'Ativar', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Desativar', exact: true })).toBeVisible();
  conferir(link.id, { ativo: true });
  await page.getByRole('button', { name: 'Excluir', exact: true }).click();
  await page
    .getByRole('dialog', { name: 'Excluir link' })
    .getByRole('button', { name: 'Cancelar' })
    .click();
  conferir(link.id, { excluido: false });
  await page.getByRole('button', { name: 'Excluir', exact: true }).click();
  await page.getByRole('button', { name: 'Confirmar exclusão' }).click();
  await expect(page.getByText('Seu primeiro link começa aqui')).toBeVisible();
  conferir(link.id, { ativo: false, excluido: true });
  await publico(page, 'integrado-novo', 404);
  await publico(page, 'inexistente', 404);
  expect((await escrever(page, 'POST', '/api/links', dados('integrado-novo'))).status()).toBe(409);
  // Chamada anônima sem cookies: não utiliza context.request autenticado.
  const anonimo = await context.browser()!.newContext();
  try {
    const r = await anonimo.request.get(origem + '/r/integrado-novo', { maxRedirects: 0 });
    expect(r.status()).toBe(404);
  } finally {
    await anonimo.close();
  }
});

test('integrado real: paginação, ordenação, IDOR, CSRF, Origin, expiração e erros neutros', async ({
  page,
  browser,
}) => {
  await entrar(page);
  const ids = [];
  for (let i = 0; i < 11; i++) {
    const r = await escrever(page, 'POST', '/api/links', dados(`pagina-${i}`));
    expect(r.status()).toBe(201);
    ids.push((await r.json()).id as string);
  }
  await page.reload();
  await expect(page.getByText('Página 1 de 2')).toBeVisible();
  const primeira = await page.request.get(api + '/api/links?pagina=1&tamanho=10');
  expect((await primeira.json()).itens.map((i: { id: string }) => i.id)).toEqual(
    ids.slice().reverse().slice(0, 10),
  );
  await page.getByRole('button', { name: 'Próxima' }).click();
  await expect(page.getByText('Página 2 de 2')).toBeVisible();
  const segunda = await page.request.get(api + '/api/links?pagina=2&tamanho=10');
  expect((await segunda.json()).itens[0].id).toBe(ids[0]);
  const outro = await browser.newContext();
  const paginaOutro = await outro.newPage();
  try {
    await entrar(paginaOutro, 'outro@example.com');
    await expect(paginaOutro.getByText('Seu primeiro link começa aqui')).toBeVisible();
    for (const metodo of ['GET', 'PATCH', 'DELETE']) {
      const r =
        metodo === 'GET'
          ? await paginaOutro.request.get(api + '/api/links/' + ids[0])
          : await escrever(
              paginaOutro,
              metodo,
              '/api/links/' + ids[0],
              metodo === 'PATCH' ? { nome: 'Não alterar' } : undefined,
            );
      expect(r.status()).toBe(404);
      expect((await r.json()).erro.codigo).toBe('link_nao_encontrado');
    }
  } finally {
    await outro.close();
  }
  const csrfAtual = await csrf(page);
  for (const valor of [undefined, '0'.repeat(64)]) {
    const r = await page.request.patch(api + '/api/links/' + ids[0], {
      data: { ativo: false },
      headers: { Origin: origem, ...(valor ? { 'X-CSRF-Token': valor } : {}) },
    });
    expect(r.status()).toBe(403);
    expect((await r.json()).erro.codigo).toBe('csrf_invalido');
  }
  const hostil = await page.request.patch(api + '/api/links/' + ids[0], {
    data: { ativo: false },
    headers: { Origin: 'https://hostil.example', 'X-CSRF-Token': csrfAtual },
  });
  expect(hostil.status()).toBe(403);
  const invalido = await escrever(page, 'POST', '/api/links', {
    ...dados('payload-invalido'),
    usuario_id: ids[0],
  });
  expect(invalido.status()).toBe(422);
  const corpo = await invalido.text();
  expect(/Traceback|sqlalchemy|asyncpg|senha_hash|token_hash/.test(corpo)).toBe(false);
  await page.getByRole('button', { name: 'Atualizar sessão' }).click();
  await expect(page.getByRole('heading', { name: 'Meus links' })).toBeVisible();
  const cookies = await page.context().cookies(api + '/api');
  const logs = readFileSync(resolve('../.postgres-teste/e2e-api.log'), 'utf8');
  expect(logs.includes(process.env.E2E_SENHA_FIXTURE!)).toBe(false);
  expect(logs.includes(csrfAtual)).toBe(false);
  for (const cookie of cookies) expect(logs.includes(cookie.value)).toBe(false);
  operarBanco('expirar');
  await page.getByRole('button', { name: 'Atualizar sessão' }).click();
  await expect(page.getByRole('form', { name: 'Login' })).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('Sua sessão expirou');
  await page.goto('/dashboard');
  await expect(page.getByRole('form', { name: 'Login' })).toBeVisible();
});

test('integrado real: UX, loading, erro e dez combinações responsivas com dados PostgreSQL', async ({
  page,
  context,
  browser,
}) => {
  await entrar(page);
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  const atuais = await (await page.request.get(api + '/api/links?pagina=1&tamanho=100')).json();
  for (const link of atuais.itens)
    expect((await escrever(page, 'DELETE', '/api/links/' + link.id)).status()).toBe(204);
  const r = await escrever(page, 'POST', '/api/links', {
    ...dados('campanha-integrada-com-endereco-longo-para-validar-quebra-de-url'),
    nome: 'Campanha integrada com nome longo para validar os cartões',
  });
  expect(r.status()).toBe(201);
  const link = await r.json();
  conferir(link.id, { ativo: true, excluido: false });
  mkdirSync(pasta, { recursive: true });
  const medidas = [];
  for (const largura of [320, 375, 768, 1024, 1440]) {
    await page.setViewportSize({ width: largura, height: 900 });
    for (const tema of ['claro', 'escuro']) {
      await page.goto('/dashboard');
      await page.evaluate((tema) => localStorage.setItem('tema', tema), tema);
      await page.reload();
      await expect(page.getByRole('heading', { name: link.nome })).toBeVisible();
      await expect(page.locator('html')).toHaveAttribute('data-tema', tema);
      expect(
        await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
      ).toBe(true);
      await page.screenshot({
        path: resolve(pasta, `lista-real-${largura}-${tema}.png`),
        fullPage: true,
        mask: [page.getByText('verificado@example.com')],
      });
      await page.getByRole('button', { name: 'Editar', exact: true }).click();
      const dialogo = page.getByRole('dialog', { name: 'Editar link' });
      await expect(dialogo.getByLabel('Nome interno')).toBeFocused();
      await page.keyboard.press('Shift+Tab');
      await expect(dialogo.getByRole('button', { name: 'Cancelar' })).toBeFocused();
      await page.keyboard.press('Tab');
      await expect(dialogo.getByLabel('Nome interno')).toBeFocused();
      await page.keyboard.press('Tab');
      await expect(dialogo.getByLabel('Slug personalizado')).toBeFocused();
      const medidasForm = await dialogo.evaluate((e) => ({
        semOverflow: e.scrollWidth <= e.clientWidth,
        naTela:
          e.getBoundingClientRect().left >= 0 &&
          e.getBoundingClientRect().right <= window.innerWidth,
        fonteLegivel: Array.from(e.querySelectorAll('input:not([type=checkbox]),textarea')).every(
          (c) => parseFloat(getComputedStyle(c).fontSize) >= 16,
        ),
        botoesAdequados: Array.from(e.querySelectorAll('button')).every(
          (c) => c.getBoundingClientRect().height >= 44,
        ),
      }));
      expect(medidasForm).toEqual({
        semOverflow: true,
        naTela: true,
        fonteLegivel: true,
        botoesAdequados: true,
      });
      expect(
        await dialogo
          .getByLabel('Slug personalizado')
          .evaluate((e) => getComputedStyle(e).boxShadow !== 'none'),
      ).toBe(true);
      await page.screenshot({
        path: resolve(pasta, `formulario-real-${largura}-${tema}.png`),
        fullPage: true,
        mask: [
          dialogo.getByLabel('Número de WhatsApp'),
          dialogo.getByLabel('Mensagem predefinida (opcional)'),
          page.getByText('verificado@example.com'),
        ],
      });
      await page.keyboard.press('Escape');
      await expect(dialogo).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Editar', exact: true })).toBeFocused();
      await page.getByRole('button', { name: 'Excluir', exact: true }).click();
      await expect(page.getByRole('dialog', { name: 'Excluir link' })).toBeVisible();
      await page
        .getByRole('dialog', { name: 'Excluir link' })
        .getByRole('button', { name: 'Cancelar' })
        .click();
      await page.getByRole('button', { name: 'Criar link', exact: true }).click();
      const criar = page.getByRole('dialog', { name: 'Criar link' });
      await criar.getByRole('button', { name: 'Salvar link' }).click();
      await expect(criar.getByLabel('Nome interno')).toBeFocused();
      const contrastes = await criar.evaluate((e) => {
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 1;
        const ctx = canvas.getContext('2d')!;
        function lum(cor: string) {
          ctx.clearRect(0, 0, 1, 1);
          ctx.fillStyle = cor;
          ctx.fillRect(0, 0, 1, 1);
          const v = Array.from(ctx.getImageData(0, 0, 1, 1).data)
            .slice(0, 3)
            .map((n) => {
              const c = n / 255;
              return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
            });
          return v[0] * 0.2126 + v[1] * 0.7152 + v[2] * 0.0722;
        }
        function contraste(a: string, b: string) {
          const x = lum(a),
            y = lum(b);
          return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
        }
        const d = getComputedStyle(e),
          b = getComputedStyle(e.querySelector('button[type=submit]')!),
          erro = getComputedStyle(e.querySelector('[role=alert]')!);
        return {
          texto: contraste(d.color, d.backgroundColor),
          botao: contraste(b.color, b.backgroundColor),
          erro: contraste(erro.color, d.backgroundColor),
        };
      });
      for (const valor of Object.values(contrastes)) expect(valor).toBeGreaterThanOrEqual(4.5);
      await criar.getByRole('button', { name: 'Cancelar' }).click();
      medidas.push({ largura, tema, ...medidasForm, contrastes });
    }
  }
  // Atrasa somente a chegada da requisição; a resposta continua sendo a da API real.
  let liberar!: () => void;
  const bloqueio = new Promise<void>((r) => {
    liberar = r;
  });
  await page.route('**/api/links?*', async (rota) => {
    await bloqueio;
    await rota.continue();
  });
  await page.reload();
  await expect(page.getByText('Carregando links…')).toBeVisible();
  liberar();
  await expect(page.getByRole('heading', { name: link.nome })).toBeVisible();
  await page.unroute('**/api/links?*');
  // Falha de rede controlada, sem substituir respostas de negócio por mocks.
  await page.route('**/api/links?*', (rota) => rota.abort('failed'));
  await page.reload();
  await expect(page.getByRole('alert')).toContainText('Não foi possível conectar');
  await page.unroute('**/api/links?*');
  await page.getByRole('button', { name: 'Tentar novamente' }).click();
  await expect(page.getByRole('heading', { name: link.nome })).toBeVisible();
  writeFileSync(
    resolve(pasta, 'layout-real.json'),
    JSON.stringify(
      {
        navegador: browser.version(),
        infraestrutura: 'API e PostgreSQL reais; apenas atraso e falha de rede injetados',
        medidas,
      },
      null,
      2,
    ) + '\n',
  );
  await page.getByRole('button', { name: 'Sair', exact: true }).click();
  await expect(page.getByRole('form', { name: 'Login' })).toBeVisible();
});
