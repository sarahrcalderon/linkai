import { test, expect, type Page } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fixtureEstatisticas } from '../src/testes/fixtureEstatisticas';

const pasta = resolve(
  process.env.E2E_PASTA_EVIDENCIAS || '../docs/relatorios/evidencias/fase5/dashboard5.4',
);
const fixture = {
  id: '22222222-2222-4222-8222-222222222222',
  nome: 'Campanha com nome longo para validar a organização dos cartões',
  slug: 'campanha-com-endereco-publico-longo-para-validar-quebra-de-url',
  numero_whatsapp: '+5511999999999',
  mensagem: 'Olá!',
  ativo: true,
  criado_em: '2026-11-06T10:00:00Z',
  atualizado_em: '2026-11-06T10:00:00Z',
};
async function simular(page: Page) {
  await page.route('**/api/estatisticas/resumo?*', (rota) =>
    rota.fulfill({
      json: fixtureEstatisticas(Number(new URL(rota.request().url()).searchParams.get('dias'))),
    }),
  );
  await page.route('**/api/usuarios/me', (rota) =>
    rota.fulfill({
      json: {
        usuario: {
          id: '11111111-1111-4111-8111-111111111111',
          nome: 'Pessoa de teste',
          email: 'fixture@example.com',
          email_verificado: true,
        },
        csrf: 'a'.repeat(64),
      },
    }),
  );
  await page.route('**/api/links**', (rota) =>
    rota.fulfill({
      json: rota.request().url().includes('?')
        ? { itens: [fixture], total: 1, pagina: 1, tamanho: 10 }
        : fixture,
    }),
  );
}

test('dashboard: CRUD de interface com API simulada e CSRF, sem serviços externos', async ({
  page,
  context,
}) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  await simular(page);
  let itens: (typeof fixture)[] = [];
  await page.route('**/api/links**', async (rota) => {
    const metodo = rota.request().method();
    if (['POST', 'PATCH', 'DELETE'].includes(metodo)) {
      expect(rota.request().headers()['x-csrf-token'] === 'a'.repeat(64)).toBe(true);
    }
    if (metodo === 'DELETE') {
      itens = [];
      await rota.fulfill({ status: 204 });
      return;
    }
    if (metodo === 'POST') {
      itens = [{ ...fixture, ...rota.request().postDataJSON() }];
      await rota.fulfill({ status: 201, json: itens[0] });
      return;
    }
    if (metodo === 'PATCH') {
      itens[0] = { ...itens[0], ...rota.request().postDataJSON() };
      await rota.fulfill({ json: itens[0] });
      return;
    }
    await rota.fulfill({
      json: rota.request().url().includes('?')
        ? { itens, total: itens.length, pagina: 1, tamanho: 10 }
        : itens[0],
    });
  });
  await page.goto('/dashboard');
  await expect(page.getByRole('heading', { name: 'Meus links' })).toBeVisible();
  await page.getByRole('button', { name: 'Criar link', exact: true }).click();
  const form = page.getByRole('dialog', { name: 'Criar link' });
  await expect(form.getByLabel('Nome interno')).toBeFocused();
  await form.getByLabel('Nome interno').fill('Campanha E2E');
  await form.getByLabel('Slug personalizado').fill('dashboard-fixture');
  await form.getByLabel('Número de WhatsApp').fill('+5511999999999');
  await form.getByLabel('Mensagem predefinida (opcional)').fill('Mensagem de fixture');
  await form.getByRole('button', { name: 'Salvar link' }).click();
  await expect(page.getByText('Link criado.', { exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Campanha E2E', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Copiar URL de Campanha E2E' }).click();
  await expect(page.getByText('URL copiada.', { exact: true })).toBeVisible();
  const copiado = await page.evaluate(() => navigator.clipboard.readText());
  expect(new URL(copiado).pathname).toBe('/r/dashboard-fixture');
  await page.getByRole('button', { name: 'Editar', exact: true }).click();
  const editar = page.getByRole('dialog', { name: 'Editar link' });
  await editar.getByLabel('Slug personalizado').fill('dashboard-renomeado');
  await editar.getByLabel('Mensagem predefinida (opcional)').fill('');
  await expect(
    editar.getByText('O endereço anterior deixará de funcionar e poderá ser utilizado novamente.'),
  ).toBeVisible();
  await editar.getByRole('button', { name: 'Salvar link' }).click();
  await expect(page.getByText('Link atualizado.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Desativar', exact: true }).click();
  await expect(page.getByText('Link desativado.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Ativar', exact: true }).click();
  await expect(page.getByText('Link ativado.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Excluir', exact: true }).click();
  await page
    .getByRole('dialog', { name: 'Excluir link' })
    .getByRole('button', { name: 'Cancelar' })
    .click();
  await expect(page.getByRole('button', { name: 'Excluir', exact: true })).toBeFocused();
  await page.getByRole('button', { name: 'Excluir', exact: true }).click();
  await page.getByRole('button', { name: 'Confirmar exclusão' }).click();
  await expect(page.getByText('Link excluído. O slug permanece reservado.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Campanha E2E', exact: true })).toHaveCount(0);
});

test('dashboard: foco nativo, contenção de Tab, Escape e descarte seguro', async ({ page }) => {
  await simular(page);
  await page.goto('/dashboard');
  await page.getByRole('button', { name: 'Criar link', exact: true }).click();
  const dialogo = page.getByRole('dialog', { name: 'Criar link' });
  await expect(dialogo.getByLabel('Nome interno')).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(dialogo.getByRole('button', { name: 'Cancelar' })).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(dialogo.getByLabel('Nome interno')).toBeFocused();
  await dialogo.getByLabel('Nome interno').fill('Alterações não salvas');
  await page.keyboard.press('Escape');
  await expect(dialogo.getByText('Descartar as alterações não salvas?')).toBeVisible();
  await dialogo.getByRole('button', { name: 'Descartar alterações' }).click();
  await expect(dialogo).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Criar link', exact: true })).toBeFocused();
});

test('dashboard: cinco larguras, dois temas, URLs longas e diálogos sem overflow', async ({
  page,
  browser,
}) => {
  await simular(page);
  mkdirSync(pasta, { recursive: true });
  const medidas = [];
  for (const largura of [320, 375, 768, 1024, 1440]) {
    await page.setViewportSize({ width: largura, height: 900 });
    for (const tema of ['claro', 'escuro']) {
      await page.goto('/dashboard');
      await page.evaluate((tema) => localStorage.setItem('tema', tema), tema);
      await page.reload();
      await expect(page.getByRole('heading', { name: fixture.nome })).toBeVisible();
      await expect(page.locator('html')).toHaveAttribute('data-tema', tema);
      const semOverflow = await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      );
      expect(semOverflow).toBe(true);
      await page.screenshot({
        path: resolve(pasta, `lista-${largura}-${tema}.png`),
        fullPage: true,
        mask: [page.getByText('fixture@example.com')],
      });
      await page.getByRole('button', { name: 'Editar', exact: true }).click();
      const dialogo = page.getByRole('dialog', { name: 'Editar link' });
      await expect(dialogo).toBeVisible();
      const layout = await dialogo.evaluate((elemento) => ({
        semOverflow: elemento.scrollWidth <= elemento.clientWidth,
        naTela:
          elemento.getBoundingClientRect().left >= 0 &&
          elemento.getBoundingClientRect().right <= window.innerWidth,
        camposLegiveis: Array.from(
          elemento.querySelectorAll('input:not([type=checkbox]),textarea'),
        ).every((c) => parseFloat(getComputedStyle(c).fontSize) >= 16),
        botoesAdequados: Array.from(elemento.querySelectorAll('button')).every(
          (b) => b.getBoundingClientRect().height >= 44,
        ),
      }));
      expect(layout).toEqual({
        semOverflow: true,
        naTela: true,
        camposLegiveis: true,
        botoesAdequados: true,
      });
      await expect(dialogo.getByLabel('Nome interno')).toBeFocused();
      await page.keyboard.press('Tab');
      await expect(dialogo.getByLabel('Slug personalizado')).toBeFocused();
      expect(
        await dialogo
          .getByLabel('Slug personalizado')
          .evaluate((e) => getComputedStyle(e).boxShadow !== 'none'),
      ).toBe(true);
      await page.screenshot({
        path: resolve(pasta, `formulario-${largura}-${tema}.png`),
        fullPage: true,
        mask: [
          dialogo.getByLabel('Número de WhatsApp'),
          dialogo.getByLabel('Mensagem predefinida (opcional)'),
          page.getByText('fixture@example.com'),
        ],
      });
      await dialogo.getByRole('button', { name: 'Cancelar' }).click();
      await page.getByRole('button', { name: 'Excluir', exact: true }).click();
      await expect(page.getByRole('dialog', { name: 'Excluir link' })).toBeVisible();
      expect(
        await page
          .getByRole('dialog', { name: 'Excluir link' })
          .evaluate((e) => e.scrollWidth <= e.clientWidth),
      ).toBe(true);
      await page
        .getByRole('dialog', { name: 'Excluir link' })
        .getByRole('button', { name: 'Cancelar' })
        .click();
      await page.getByRole('button', { name: 'Criar link', exact: true }).click();
      const criacao = page.getByRole('dialog', { name: 'Criar link' });
      await criacao.getByRole('button', { name: 'Salvar link' }).click();
      await expect(criacao.getByLabel('Nome interno')).toBeFocused();
      const contrastes = await criacao.evaluate((elemento) => {
        const tela = document.createElement('canvas');
        tela.width = tela.height = 1;
        const contexto = tela.getContext('2d')!;
        function luminancia(cor: string) {
          contexto.clearRect(0, 0, 1, 1);
          contexto.fillStyle = cor;
          contexto.fillRect(0, 0, 1, 1);
          const v = Array.from(contexto.getImageData(0, 0, 1, 1).data)
            .slice(0, 3)
            .map((n) => {
              const c = n / 255;
              return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
            });
          return v[0] * 0.2126 + v[1] * 0.7152 + v[2] * 0.0722;
        }
        function razao(a: string, b: string) {
          const x = luminancia(a),
            y = luminancia(b);
          return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
        }
        const dialogo = getComputedStyle(elemento);
        const botao = getComputedStyle(elemento.querySelector('button[type=submit]')!);
        const erro = getComputedStyle(elemento.querySelector('[role=alert]')!);
        return {
          texto: razao(dialogo.color, dialogo.backgroundColor),
          botao: razao(botao.color, botao.backgroundColor),
          erro: razao(erro.color, dialogo.backgroundColor),
        };
      });
      for (const contraste of Object.values(contrastes))
        expect(contraste).toBeGreaterThanOrEqual(4.5);
      expect(await criacao.evaluate((e) => e.scrollWidth <= e.clientWidth)).toBe(true);
      medidas.push({ largura, tema, listaSemOverflow: semOverflow, ...layout, contrastes });
      await page.screenshot({
        path: resolve(pasta, `validacao-${largura}-${tema}.png`),
        fullPage: true,
        mask: [page.getByText('fixture@example.com')],
      });
      await criacao.getByRole('button', { name: 'Cancelar' }).click();
    }
  }
  writeFileSync(
    resolve(pasta, 'dashboard-layout.json'),
    JSON.stringify({ navegador: browser.version(), medidas }, null, 2) + '\n',
  );
});
