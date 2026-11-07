import { test, expect, type Page } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';

const pasta = resolve('../docs/relatorios/evidencias/fase6/dashboard6.4');
const link = {
  id: '22222222-2222-4222-8222-222222222222',
  nome: 'Campanha Analytics',
  slug: 'campanha-analytics',
  ativo: true,
  numero_whatsapp: '+5511999999999',
  mensagem: null,
  criado_em: '2026-01-01T00:00:00Z',
  atualizado_em: '2026-01-01T00:00:00Z',
};
function estatisticas(dias: number, total = 14) {
  return {
    total_acessos: total,
    links_ativos: 1,
    links_inativos: 0,
    link_id: link.id,
    data_inicial: '2026-01-01T00:00:00Z',
    data_final: new Date(Date.UTC(2026, 0, dias, 12)).toISOString(),
    serie_diaria: Array.from({ length: dias }, (_, i) => ({
      data: new Date(Date.UTC(2026, 0, i + 1)).toISOString().slice(0, 10),
      acessos: i === 0 ? total : 0,
    })),
  };
}
async function simular(page: Page, tema = 'claro') {
  await page.addInitScript((valor) => localStorage.setItem('tema', valor), tema);
  await page.route('**/api/**', async (rota) => {
    const url = new URL(rota.request().url());
    if (url.pathname === '/api/usuarios/me')
      return rota.fulfill({
        json: {
          usuario: {
            id: '11111111-1111-4111-8111-111111111111',
            nome: 'Pessoa de teste',
            email: 'fixture@example.com',
            email_verificado: true,
          },
          csrf: 'a'.repeat(64),
        },
      });
    if (url.pathname.includes('estatisticas'))
      return rota.fulfill({ json: estatisticas(Number(url.searchParams.get('dias'))) });
    if (url.pathname === '/api/links')
      return rota.fulfill({ json: { itens: [link], total: 1, pagina: 1, tamanho: 10 } });
    return rota.fulfill({ status: 404, json: {} });
  });
}
for (const largura of [320, 375, 768, 1024, 1440]) {
  for (const tema of ['claro', 'escuro']) {
    test(`Analytics ${largura}px tema ${tema}: layout, teclado e tabela`, async ({ page }) => {
      await page.setViewportSize({ width: largura, height: 1000 });
      await simular(page, tema);
      await page.goto('/dashboard');
      const analytics = page.locator('#analytics');
      await expect(analytics.locator('article').getByText('14', { exact: true })).toBeVisible();
      await expect(page.locator('html')).toHaveAttribute('data-tema', tema);
      await expect(analytics.getByLabel('Período')).toHaveCSS('min-height', '44px');
      await analytics.getByLabel('Período').selectOption('90');
      await expect(analytics.getByText(/Últimos 90 dias · UTC/)).toBeVisible();
      const slider = analytics.getByRole('slider');
      await slider.focus();
      await expect(slider).toBeFocused();
      await expect(slider).toHaveCSS('outline-style', 'solid');
      await slider.press('ArrowRight');
      await expect(slider).toHaveAttribute('aria-valuetext', '02/01: 0 acessos');
      await analytics.getByText('Ver tabela diária').click();
      await expect(analytics.getByRole('table')).toBeVisible();
      await expect(analytics.getByRole('row')).toHaveCount(91);
      const dimensoes = await page.evaluate(() => ({
        largura: innerWidth,
        conteudo: document.documentElement.scrollWidth,
        tema: document.documentElement.dataset.tema,
      }));
      expect(dimensoes.conteudo).toBeLessThanOrEqual(largura);
      const contraste = await page.evaluate(() => {
        const contexto = document.createElement('canvas').getContext('2d')!;
        function luminancia(cor: string) {
          contexto.fillStyle = cor;
          contexto.fillRect(0, 0, 1, 1);
          const rgb = [...contexto.getImageData(0, 0, 1, 1).data].slice(0, 3).map((v) => {
            const n = v / 255;
            return n <= 0.04045 ? n / 12.92 : ((n + 0.055) / 1.055) ** 2.4;
          });
          return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
        }
        const fundo = luminancia(getComputedStyle(document.querySelector('main')!).backgroundColor);
        const texto = luminancia(
          getComputedStyle(document.querySelector('#titulo-analytics')!).color,
        );
        const linha = luminancia(
          getComputedStyle(document.querySelector('#analytics svg[role="img"]')!).color,
        );
        const razao = (valor: number) =>
          (Math.max(valor, fundo) + 0.05) / (Math.min(valor, fundo) + 0.05);
        return { texto: razao(texto), linha: razao(linha) };
      });
      expect(contraste.texto).toBeGreaterThanOrEqual(4.5);
      expect(contraste.linha).toBeGreaterThanOrEqual(3);
      mkdirSync(pasta, { recursive: true });
      await analytics.screenshot({ path: resolve(pasta, `analytics-${largura}-${tema}.png`) });
      writeFileSync(
        resolve(pasta, `layout-${largura}-${tema}.json`),
        JSON.stringify({ ...dimensoes, contraste }, null, 2) + '\n',
      );
    });
  }
}
test('seleciona link próprio e retorna ao resumo sem lista adicional', async ({ page }) => {
  let listas = 0;
  page.on('request', (req) => {
    if (new URL(req.url()).pathname === '/api/links') listas++;
  });
  await simular(page);
  await page.goto('/dashboard');
  await expect(
    page.getByRole('button', { name: 'Estatísticas de Campanha Analytics' }),
  ).toBeVisible();
  const listasIniciais = listas;
  await page.getByRole('button', { name: 'Estatísticas de Campanha Analytics' }).click();
  await expect(
    page.getByRole('heading', { name: 'Estatísticas de Campanha Analytics' }),
  ).toBeFocused();
  await expect(page.locator('#analytics').getByText(/\/r\/campanha-analytics$/)).toBeVisible();
  await expect(page.locator('#analytics').getByText('Links ativos')).toHaveCount(0);
  await page.getByRole('button', { name: 'Voltar à visão geral' }).click();
  await expect(page.locator('#analytics').getByText('Links ativos')).toBeVisible();
  expect(listas).toBe(listasIniciais);
});
test('rede indisponível, repetição e período sem acessos', async ({ page }) => {
  await simular(page);
  await page.route('**/api/estatisticas/resumo?*', (rota) => rota.abort('connectionfailed'));
  await page.goto('/dashboard');
  await expect(page.locator('#analytics').getByRole('alert')).toContainText(
    'Verifique sua conexão',
  );
  await page.unroute('**/api/estatisticas/resumo?*');
  await page.route('**/api/estatisticas/resumo?*', (rota) =>
    rota.fulfill({ json: estatisticas(7, 0) }),
  );
  await page.getByRole('button', { name: 'Tentar novamente', exact: true }).click();
  await expect(page.getByText('Nenhum acesso registrado neste período.')).toBeVisible();
});
test('401 de métricas encerra a sessão pela proteção existente', async ({ page }) => {
  await simular(page);
  await page.route('**/api/estatisticas/resumo?*', (rota) =>
    rota.fulfill({ status: 401, json: {} }),
  );
  await page.goto('/dashboard');
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByText('Sua sessão expirou. Entre novamente.')).toBeVisible();
});

test('troca rápida de período não mostra resposta antiga e mantém loading', async ({ page }) => {
  await simular(page);
  let liberar!: () => void;
  const espera = new Promise<void>((resolver) => {
    liberar = resolver;
  });
  await page.route('**/api/estatisticas/resumo?dias=30', async (rota) => {
    await espera;
    await rota.fulfill({ json: estatisticas(30, 300) });
  });
  await page.goto('/dashboard');
  const painel = page.locator('#analytics');
  await expect(painel.locator('article').getByText('14', { exact: true })).toBeVisible();
  const requisicao = page.waitForRequest('**/api/estatisticas/resumo?dias=30');
  await painel.getByLabel('Período').selectOption('30');
  await requisicao;
  await expect(painel.getByRole('status')).toHaveText('Carregando estatísticas…');
  await expect(painel.locator('article')).toHaveCount(0);
  await painel.getByLabel('Período').selectOption('90');
  await expect(painel.getByText(/Últimos 90 dias · UTC/)).toBeVisible();
  const respostaAntiga = page.waitForResponse('**/api/estatisticas/resumo?dias=30');
  liberar();
  await respostaAntiga;
  await expect(painel.locator('article').getByText('300', { exact: true })).toHaveCount(0);
  await expect(painel.getByText(/Últimos 90 dias · UTC/)).toBeVisible();
});
test('link removido ou não autorizado não revela estatísticas', async ({ page }) => {
  await simular(page);
  await page.route('**/api/links/*/estatisticas?*', (rota) =>
    rota.fulfill({ status: 404, json: {} }),
  );
  await page.goto('/dashboard');
  await page.getByRole('button', { name: 'Estatísticas de Campanha Analytics' }).click();
  await expect(page.locator('#analytics').getByRole('alert')).toContainText('Link indisponível');
  await expect(page.locator('#analytics').getByRole('img')).toHaveCount(0);
});
