import { test, expect, type Page } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { operarBanco } from './ambiente';

const api = 'http://127.0.0.1:18000';
const origem = 'http://127.0.0.1:15173';
const pasta = resolve(
  process.env.E2E_PASTA_EVIDENCIAS || '../docs/relatorios/evidencias/fase6/integrada6.5',
);
type Estatisticas = {
  total_acessos: number;
  data_inicial: string;
  data_final: string;
  serie_diaria: { data: string; acessos: number }[];
  links_ativos?: number;
  links_inativos?: number;
};
function banco(entrada: object) {
  return JSON.parse(
    execFileSync(
      process.env.E2E_PYTHON || resolve('../backend/.venv/Scripts/python.exe'),
      ['-m', 'testes.e2e.analytics'],
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
function salvar(nome: string, dados: object) {
  mkdirSync(pasta, { recursive: true });
  writeFileSync(resolve(pasta, nome + '.json'), JSON.stringify(dados, null, 2) + '\n');
}
async function entrar(page: Page, email = 'verificado@example.com') {
  await page.goto('/login');
  await page.getByLabel('E-mail', { exact: true }).fill(email);
  await page.getByLabel('Senha', { exact: true }).fill(process.env.E2E_SENHA_FIXTURE!);
  await page.getByRole('button', { name: 'Entrar', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Meus links' })).toBeVisible();
  await expect(page.locator('#analytics').getByText('Links ativos')).toBeVisible();
}
async function consultar(page: Page, dias = 7, id?: string): Promise<Estatisticas> {
  const r = await page.request.get(
    api + (id ? `/api/links/${id}/estatisticas` : '/api/estatisticas/resumo') + `?dias=${dias}`,
  );
  expect(r.status()).toBe(200);
  expect(r.headers()['cache-control']).toBe('private, no-store');
  const dados = await r.json();
  expect(Object.keys(dados).sort()).toEqual(
    (id
      ? ['link_id', 'total_acessos', 'data_inicial', 'data_final', 'serie_diaria']
      : [
          'links_ativos',
          'links_inativos',
          'total_acessos',
          'data_inicial',
          'data_final',
          'serie_diaria',
        ]
    ).sort(),
  );
  return dados;
}
function conferirSQL(dados: Estatisticas, id?: string, email?: string) {
  const sql = banco({
    operacao: 'consultar',
    inicio: dados.data_inicial,
    fim: dados.data_final,
    id,
    email,
  });
  expect(dados.total_acessos).toBe(sql.total);
  for (const dia of dados.serie_diaria) expect(dia.acessos).toBe(sql.diarios[dia.data] || 0);
  if (!id) {
    expect(dados.links_ativos).toBe(sql.ativos);
    expect(dados.links_inativos).toBe(sql.inativos);
  }
  return sql;
}
async function escrever(page: Page, metodo: string, caminho: string, dados?: object) {
  const me = await page.request.get(api + '/api/usuarios/me');
  const csrf = (await me.json()).csrf;
  return page.request.fetch(api + caminho, {
    method: metodo,
    headers: { Origin: origem, 'X-CSRF-Token': csrf },
    ...(dados ? { data: dados } : {}),
  });
}
async function acessar(page: Page, slug: string) {
  const inicio = performance.now();
  const r = await page.request.get(origem + '/r/' + slug, { maxRedirects: 0 });
  expect(r.status()).toBe(302);
  expect(new URL(r.headers().location).origin).toBe('https://wa.me');
  expect(r.headers()['cache-control']).toContain('no-store');
  return performance.now() - inicio;
}
async function esperarEventos(id: string, eventos: number) {
  await expect
    .poll(() => banco({ operacao: 'contar', id }).eventos, { timeout: 10000 })
    .toBe(eventos);
}
test.beforeEach(async ({ context }) => {
  operarBanco('preparar');
  // Guarda de rede, sem substituir nenhuma resposta de negócio.
  await context.route('**/*', (rota) => {
    if (!['127.0.0.1', 'localhost'].includes(new URL(rota.request().url()).hostname))
      throw new Error('Destino externo bloqueado na homologação.');
    return rota.continue();
  });
});

test('Analytics real: cadastro local, dashboard, três 302, SQL, concorrência e falha best effort', async ({
  page,
}) => {
  await entrar(page);
  await page.getByRole('button', { name: 'Criar link', exact: true }).click();
  const form = page.getByRole('dialog', { name: 'Criar link' });
  await form.getByLabel('Nome interno').fill('Campanha integrada Analytics');
  await form.getByLabel('Slug personalizado').fill('analytics-integrado');
  await form.getByLabel('Número de WhatsApp').fill('+5511999999999');
  await form.getByRole('button', { name: 'Salvar link' }).click();
  await expect(page.getByText('Link criado.', { exact: true })).toBeVisible();
  const lista = await page.request.get(api + '/api/links?pagina=1&tamanho=10');
  const link = (await lista.json()).itens[0];
  expect(banco({ operacao: 'contar', id: link.id })).toEqual({ link_persistido: true, eventos: 0 });
  const inicial = await consultar(page);
  expect(inicial.total_acessos).toBe(0);
  conferirSQL(inicial);
  await expect(page.getByText('Nenhum acesso registrado neste período.')).toBeVisible();
  const temposIniciais = [];
  for (let i = 0; i < 3; i++) temposIniciais.push(await acessar(page, link.slug));
  await esperarEventos(link.id, 3);
  await page.reload();
  const painel = page.locator('#analytics');
  await expect(painel.locator('article').getByText('3', { exact: true })).toBeVisible();
  const atual = await consultar(page);
  expect(atual.total_acessos).toBe(3);
  conferirSQL(atual);
  expect(atual.serie_diaria.at(-1)?.acessos).toBe(3);
  await painel.getByText('Ver tabela diária').click();
  await expect(painel.getByRole('cell', { name: '3', exact: true })).toBeVisible();
  await painel.getByRole('slider').press('End');
  await expect(painel.getByRole('tooltip')).toContainText('3 acessos registrados');
  const temposConcorrentes = await Promise.all(
    Array.from({ length: 20 }, () => acessar(page, link.slug)),
  );
  await esperarEventos(link.id, 23);
  expect((await consultar(page)).total_acessos).toBe(23);
  const logAntes = readFileSync(resolve('../.postgres-teste/e2e-api.log'), 'utf8');
  const falhasAntes = (logAntes.match(/evento_acesso_nao_confirmado categoria=integridade/g) || [])
    .length;
  banco({ operacao: 'falhar', id: link.id });
  try {
    await Promise.all(Array.from({ length: 3 }, () => acessar(page, link.slug)));
    await expect
      .poll(
        () => {
          const log = readFileSync(resolve('../.postgres-teste/e2e-api.log'), 'utf8');
          return (
            (log.match(/evento_acesso_nao_confirmado categoria=integridade/g) || []).length -
            falhasAntes
          );
        },
        { timeout: 10000 },
      )
      .toBe(3);
    expect(banco({ operacao: 'contar', id: link.id }).eventos).toBe(23);
    await page.reload();
    await expect(painel.locator('article').getByText('23', { exact: true })).toBeVisible();
    conferirSQL(await consultar(page));
    // Espera limitada adicional para observar ausência de retentativa de falhas.
    await page.waitForTimeout(750);
    const log = readFileSync(resolve('../.postgres-teste/e2e-api.log'), 'utf8');
    expect(
      (log.match(/evento_acesso_nao_confirmado categoria=integridade/g) || []).length - falhasAntes,
    ).toBe(3);
  } finally {
    banco({ operacao: 'restaurar' });
  }
  const medidas = {
    sequenciaisMs: temposIniciais,
    concorrentesMs: temposConcorrentes,
    recebidos: 26,
    respostas302: 26,
    persistidos: 23,
    falhasControladas: 3,
    observacao: 'Ensaio local de 20 simultâneos, sem SLA; best effort pode perder eventos.',
  };
  salvar('fluxo-concorrencia', medidas);
});

test('Analytics real: períodos UTC, estados, múltiplos links e usuários, SQL e segurança', async ({
  page,
  browser,
}) => {
  const ids = banco({ operacao: 'semear' });
  await entrar(page);
  const resultados = [];
  const painel = page.locator('#analytics');
  for (const dias of [7, 30, 90]) {
    await painel.getByLabel('Período').selectOption(String(dias));
    await expect(painel.getByText(new RegExp(`Últimos ${dias} dias · UTC`))).toBeVisible();
    const dados = await consultar(page, dias);
    expect(dados.serie_diaria).toHaveLength(dias);
    expect(dados.serie_diaria.some((d) => d.acessos === 0)).toBe(true);
    expect(dados.total_acessos).toBe(dias === 7 ? 6 : 10);
    expect(dados.links_ativos).toBe(2);
    expect(dados.links_inativos).toBe(1);
    conferirSQL(dados);
    await expect(
      painel.locator('article').getByText(String(dados.total_acessos), { exact: true }),
    ).toBeVisible();
    await painel.getByText('Ver tabela diária').click();
    await expect(painel.getByRole('row')).toHaveCount(dias + 1);
    await painel.getByText('Ver tabela diária').click();
    for (const slug of ['historico', 'historico-inativo', 'sem-acessos']) {
      const individual = await consultar(page, dias, ids[slug]);
      conferirSQL(individual, ids[slug]);
    }
    resultados.push({ dias, total: dados.total_acessos, serie: dados.serie_diaria });
  }
  const outro = await browser.newContext();
  try {
    const paginaOutro = await outro.newPage();
    await entrar(paginaOutro, 'outro@example.com');
    conferirSQL(await consultar(paginaOutro), undefined, 'outro@example.com');
    const alheio = await paginaOutro.request.get(api + `/api/links/${ids.historico}/estatisticas`);
    const inexistente = await paginaOutro.request.get(
      api + '/api/links/99999999-9999-4999-8999-999999999999/estatisticas',
    );
    expect(alheio.status()).toBe(404);
    expect(inexistente.status()).toBe(404);
    expect(await alheio.json()).toEqual(await inexistente.json());
    expect(alheio.headers()['cache-control']).toBe('private, no-store');
  } finally {
    await outro.close();
  }
  const anonimo = await browser.newContext();
  try {
    for (const caminho of [
      '/api/estatisticas/resumo',
      `/api/links/${ids.historico}/estatisticas`,
    ]) {
      const r = await anonimo.request.get(api + caminho);
      expect(r.status()).toBe(401);
      expect(r.headers()['cache-control']).toBe('private, no-store');
    }
  } finally {
    await anonimo.close();
  }
  const excluido = await page.request.get(
    api + `/api/links/${ids['historico-excluido']}/estatisticas`,
  );
  expect(excluido.status()).toBe(404);
  const dadosCriacao = {
    nome: 'Prova CSRF',
    slug: 'prova-csrf',
    numero_whatsapp: '+5511999999999',
  };
  const semCsrf = await page.request.post(api + '/api/links', {
    headers: { Origin: origem },
    data: dadosCriacao,
  });
  expect(semCsrf.status()).toBe(403);
  const me = await page.request.get(api + '/api/usuarios/me');
  const token = (await me.json()).csrf;
  const origemInvalida = await page.request.post(api + '/api/links', {
    headers: { Origin: 'https://invalida.example', 'X-CSRF-Token': token },
    data: dadosCriacao,
  });
  expect(origemInvalida.status()).toBe(403);
  const correto = await escrever(page, 'POST', '/api/links', {
    ...dadosCriacao,
    slug: 'csrf-correto',
  });
  expect(correto.status()).toBe(201);
  salvar('periodos-sql-seguranca', {
    resultados,
    idor: '404 indistinguível de inexistente',
    csrf: '403 sem token/origem inválida; 201 com ambos válidos',
  });
  operarBanco('expirar');
  const expirado = await page.request.get(api + '/api/estatisticas/resumo');
  expect(expirado.status()).toBe(401);
  expect(expirado.headers()['cache-control']).toBe('private, no-store');
  await page.reload();
  await expect(page).toHaveURL(/\/login$/);
});

test('Analytics real: dez layouts, temas, teclado, contraste, loading e erro de rede', async ({
  page,
  browser,
}) => {
  banco({ operacao: 'semear' });
  await entrar(page);
  const medidas = [];
  const painel = page.locator('#analytics');
  for (const largura of [320, 375, 768, 1024, 1440]) {
    await page.setViewportSize({ width: largura, height: 1000 });
    for (const tema of ['claro', 'escuro']) {
      if ((await page.locator('html').getAttribute('data-tema')) !== tema)
        await page.getByRole('button', { name: `Ativar tema ${tema}` }).click();
      const slider = painel.getByRole('slider');
      await painel.getByLabel('Período').focus();
      await page.keyboard.press('Tab');
      await expect(slider).toBeFocused();
      await expect(slider).toHaveCSS('outline-style', 'solid');
      await slider.press('Home');
      await slider.press('ArrowRight');
      await expect(slider).toHaveValue('1');
      await expect(painel.getByRole('tooltip')).toBeVisible();
      await painel.getByText('Ver tabela diária').click();
      await expect(painel.getByRole('row')).toHaveCount(8);
      const medida = await page.evaluate(() => {
        const ctx = document.createElement('canvas').getContext('2d')!;
        function lum(cor: string) {
          ctx.fillStyle = cor;
          ctx.fillRect(0, 0, 1, 1);
          const rgb = [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3).map((n) => {
            const v = n / 255;
            return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
          });
          return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
        }
        const fundo = lum(getComputedStyle(document.querySelector('main')!).backgroundColor);
        function contraste(seletor: string) {
          const texto = lum(getComputedStyle(document.querySelector(seletor)!).color);
          return (Math.max(fundo, texto) + 0.05) / (Math.min(fundo, texto) + 0.05);
        }
        return {
          conteudo: document.documentElement.scrollWidth,
          texto: contraste('#titulo-analytics'),
          linha: contraste('#analytics svg[role=img]'),
        };
      });
      expect(medida.conteudo).toBeLessThanOrEqual(largura);
      expect(medida.texto).toBeGreaterThanOrEqual(4.5);
      expect(medida.linha).toBeGreaterThanOrEqual(3);
      mkdirSync(pasta, { recursive: true });
      await painel.screenshot({ path: resolve(pasta, `real-${largura}-${tema}.png`) });
      medidas.push({ largura, tema, ...medida });
      await painel.getByText('Ver tabela diária').click();
    }
  }
  await page.getByRole('button', { name: 'Estatísticas de sem-acessos' }).click();
  await expect(page.getByRole('heading', { name: 'Estatísticas de sem-acessos' })).toBeFocused();
  await expect(page.getByText('Nenhum acesso registrado neste período.')).toBeVisible();
  await page.getByRole('button', { name: 'Voltar à visão geral' }).click();
  let liberar!: () => void;
  const espera = new Promise<void>((r) => {
    liberar = r;
  });
  await page.route('**/api/estatisticas/resumo?*', async (rota) => {
    await espera;
    await rota.continue();
  });
  await page.reload();
  await expect(painel.getByRole('status')).toHaveText('Carregando estatísticas…');
  liberar();
  await expect(painel.getByText('Links ativos')).toBeVisible();
  await page.unroute('**/api/estatisticas/resumo?*');
  await page.route('**/api/estatisticas/resumo?*', (rota) => rota.abort('connectionfailed'));
  await page.reload();
  await expect(painel.getByRole('alert')).toContainText('Verifique sua conexão');
  await page.unroute('**/api/estatisticas/resumo?*');
  await painel.getByRole('button', { name: 'Tentar novamente' }).click();
  await expect(painel.getByText('Links ativos')).toBeVisible();
  const logs = readFileSync(resolve('../.postgres-teste/e2e-api.log'), 'utf8');
  expect(logs.includes(process.env.E2E_SENHA_FIXTURE!)).toBe(false);
  expect(
    /linkai_sessao=|X-CSRF-Token:|authorization:|5511999999999|senha_hash|token_hash/i.test(logs),
  ).toBe(false);
  expect(await page.evaluate(() => Object.keys(localStorage))).toEqual(['tema']);
  expect(await page.evaluate(() => sessionStorage.length)).toBe(0);
  salvar('ux-real', {
    navegador: browser.version(),
    medidas,
    loading: 'atraso controlado com resposta real',
    erro: 'falha de transporte injetada; repetição consulta API real',
    logs: 'nenhuma credencial ou token encontrado nas verificações',
  });
});
