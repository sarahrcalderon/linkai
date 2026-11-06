import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { Aplicacao } from '../Aplicacao';
import type { LinkPersonalizado } from '../funcionalidades/links/servico';

const sessao = {
  usuario: {
    id: '11111111-1111-4111-8111-111111111111',
    nome: 'Ana',
    email: 'ana@example.com',
    email_verificado: true,
  },
  csrf: 'f'.repeat(64),
};
const exemplo: LinkPersonalizado = {
  id: '22222222-2222-4222-8222-222222222222',
  nome: 'Campanha',
  slug: 'campanha',
  numero_whatsapp: '+5511999999999',
  mensagem: 'Olá!',
  ativo: true,
  criado_em: '2026-11-06T10:00:00Z',
  atualizado_em: '2026-11-06T10:00:00Z',
};
const buscar = vi.fn<typeof fetch>();
const resposta = (status: number, dados?: unknown) =>
  new Response(status === 204 ? null : JSON.stringify(dados), { status });
let itens: LinkPersonalizado[];
async function api(url: RequestInfo | URL, opcoes?: RequestInit): Promise<Response> {
  const endereco = new URL(String(url));
  if (endereco.pathname.endsWith('/usuarios/me')) return resposta(200, sessao);
  if (endereco.pathname === '/api/links') {
    if (opcoes?.method === 'POST') {
      const link = { ...exemplo, ...JSON.parse(String(opcoes.body)) };
      itens = [link, ...itens];
      return resposta(201, link);
    }
    const pagina = Number(endereco.searchParams.get('pagina'));
    return resposta(200, {
      itens: itens.slice((pagina - 1) * 10, pagina * 10),
      total: itens.length,
      pagina,
      tamanho: 10,
    });
  }
  const id = endereco.pathname.split('/').pop();
  const link = itens.find((i) => i.id === id);
  if (!link) return resposta(404, { erro: { codigo: 'link_nao_encontrado' } });
  if (opcoes?.method === 'DELETE') {
    itens = itens.filter((i) => i.id !== id);
    return resposta(204);
  }
  if (opcoes?.method === 'PATCH') {
    Object.assign(link, JSON.parse(String(opcoes.body)));
    return resposta(200, link);
  }
  return resposta(200, link);
}
beforeEach(() => {
  itens = [{ ...exemplo }];
  buscar.mockReset();
  buscar.mockImplementation(api);
  vi.stubGlobal('fetch', buscar);
  localStorage.clear();
  sessionStorage.clear();
  window.history.replaceState(null, '', '/dashboard');
  vi.stubGlobal(
    'navigator',
    Object.assign(Object.create(navigator), {
      clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
    }),
  );
  HTMLDialogElement.prototype.showModal = function () {
    this.setAttribute('open', '');
    this.querySelector<HTMLElement>('input,button')?.focus();
  };
  HTMLDialogElement.prototype.close = function () {
    this.removeAttribute('open');
  };
});
afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, '', '/');
});
async function abrir() {
  await act(async () => {
    render(
      <StrictMode>
        <Aplicacao />
      </StrictMode>,
    );
  });
}
async function editar() {
  fireEvent.click(await screen.findByRole('button', { name: 'Editar' }));
  return await screen.findByRole('dialog', { name: 'Editar link' });
}
function preencher() {
  fireEvent.change(screen.getByLabelText('Nome interno'), { target: { value: 'Nova campanha' } });
  fireEvent.change(screen.getByLabelText('Slug personalizado'), {
    target: { value: 'nova-campanha' },
  });
  fireEvent.change(screen.getByLabelText('Número de WhatsApp'), {
    target: { value: '+5511888888888' },
  });
}
const escritas = () =>
  buscar.mock.calls.filter(([, o]) => ['POST', 'PATCH', 'DELETE'].includes(o?.method || ''));

it('renderiza lista, URL completa, estado e ações sem métricas fictícias', async () => {
  await abrir();
  expect(await screen.findByRole('heading', { name: 'Campanha' })).toBeVisible();
  expect(screen.getByText('Ativo')).toBeVisible();
  expect(screen.getByRole('link', { name: 'Abrir Campanha' })).toHaveAttribute(
    'href',
    expect.stringContaining('/r/campanha'),
  );
  expect(screen.queryByText(/cliques|estatísticas estarão/)).not.toBeInTheDocument();
});
it('mostra estado vazio e ação principal', async () => {
  itens = [];
  await abrir();
  expect(await screen.findByText('Seu primeiro link começa aqui')).toBeVisible();
  expect(screen.getByRole('button', { name: 'Criar link' })).toBeEnabled();
});
it('cria com cookies e CSRF, sem proprietário fornecido pelo cliente', async () => {
  itens = [];
  await abrir();
  await screen.findByText('Seu primeiro link começa aqui');
  fireEvent.click(screen.getByRole('button', { name: 'Criar link' }));
  preencher();
  fireEvent.click(screen.getByRole('button', { name: 'Salvar link' }));
  expect(await screen.findByText('Link criado.')).toBeVisible();
  const opcoes = escritas()[0][1];
  expect(opcoes?.credentials).toBe('include');
  expect(opcoes?.headers).toMatchObject({ 'X-CSRF-Token': sessao.csrf });
  expect(JSON.parse(String(opcoes?.body))).toEqual({
    nome: 'Nova campanha',
    slug: 'nova-campanha',
    numero_whatsapp: '+5511888888888',
    mensagem: null,
  });
  expect(sessionStorage.length).toBe(0);
  expect(Object.keys(localStorage)).toEqual(['tema']);
});
it('valida campos e foca primeiro erro sem enviar', async () => {
  await abrir();
  fireEvent.click(await screen.findByRole('button', { name: 'Criar link' }));
  fireEvent.click(screen.getByRole('button', { name: 'Salvar link' }));
  expect(screen.getByLabelText('Nome interno')).toHaveFocus();
  expect(screen.getByLabelText('Slug personalizado')).toHaveAttribute('aria-invalid', 'true');
  expect(escritas()).toHaveLength(0);
});
it('trata conflito 409 junto ao slug, sem afirmar disponibilidade', async () => {
  buscar.mockImplementation(async (u, o) =>
    o?.method === 'POST' ? resposta(409, { erro: { codigo: 'slug_indisponivel' } }) : api(u, o),
  );
  await abrir();
  fireEvent.click(await screen.findByRole('button', { name: 'Criar link' }));
  preencher();
  expect(screen.getByText(/A disponibilidade será confirmada/)).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Salvar link' }));
  await waitFor(() =>
    expect(screen.getByLabelText('Slug personalizado')).toHaveAttribute('aria-invalid', 'true'),
  );
});
it('edita apenas campo alterado e permite limpar mensagem com null', async () => {
  await abrir();
  const dialogo = await editar();
  fireEvent.change(within(dialogo).getByLabelText('Mensagem predefinida (opcional)'), {
    target: { value: '' },
  });
  fireEvent.click(screen.getByRole('button', { name: 'Salvar link' }));
  expect(await screen.findByText('Link atualizado.')).toBeVisible();
  expect(JSON.parse(String(escritas()[0][1]?.body))).toEqual({ mensagem: null });
});
it('mostra aviso de renomeação e protege alterações ao cancelar', async () => {
  await abrir();
  await editar();
  fireEvent.change(screen.getByLabelText('Slug personalizado'), {
    target: { value: 'outro-slug' },
  });
  expect(
    screen.getByText('O endereço anterior deixará de funcionar e poderá ser utilizado novamente.'),
  ).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
  expect(screen.getByText('Descartar as alterações não salvas?')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Continuar editando' }));
  expect(screen.getByRole('dialog')).toBeVisible();
  fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
  fireEvent.click(screen.getByRole('button', { name: 'Descartar alterações' }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(escritas()).toHaveLength(0);
});
it('ativa e desativa com PATCH mínimo', async () => {
  await abrir();
  fireEvent.click(await screen.findByRole('button', { name: 'Desativar' }));
  expect(await screen.findByText('Link desativado.')).toBeVisible();
  fireEvent.click(await screen.findByRole('button', { name: 'Ativar' }));
  expect(await screen.findByText('Link ativado.')).toBeVisible();
  expect(escritas().map(([, o]) => JSON.parse(String(o?.body)))).toEqual([
    { ativo: false },
    { ativo: true },
  ]);
});
it('exclusão exige confirmação e permite cancelar com retorno de foco', async () => {
  await abrir();
  const botao = await screen.findByRole('button', { name: 'Excluir' });
  botao.focus();
  fireEvent.click(botao);
  const dialogo = screen.getByRole('dialog', { name: 'Excluir link' });
  expect(within(dialogo).getByText(/slug vigente permanecerá reservado/)).toBeVisible();
  fireEvent.click(within(dialogo).getByRole('button', { name: 'Cancelar' }));
  expect(escritas()).toHaveLength(0);
  expect(botao).toHaveFocus();
  fireEvent.click(botao);
  fireEvent.click(screen.getByRole('button', { name: 'Confirmar exclusão' }));
  expect(await screen.findByText('Link excluído. O slug permanece reservado.')).toBeVisible();
  expect(await screen.findByText('Seu primeiro link começa aqui')).toBeVisible();
  expect(escritas()).toHaveLength(1);
});
it('copia URL e anuncia feedback acessível', async () => {
  await abrir();
  fireEvent.click(await screen.findByRole('button', { name: 'Copiar URL de Campanha' }));
  expect(await screen.findByText('URL copiada.')).toHaveFocus();
  expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
    expect.stringContaining('/r/campanha'),
  );
});
it('trata falha de copiar sem alert nativo', async () => {
  vi.mocked(navigator.clipboard.writeText).mockRejectedValueOnce(new Error('bloqueado'));
  await abrir();
  fireEvent.click(await screen.findByRole('button', { name: 'Copiar URL de Campanha' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Selecione e copie');
});
it('redireciona para login quando listagem informa sessão expirada', async () => {
  buscar.mockImplementation(async (u, o) =>
    String(u).includes('/api/links') ? resposta(401) : api(u, o),
  );
  await abrir();
  expect(await screen.findByRole('form', { name: 'Login' })).toBeVisible();
  expect(screen.getByRole('alert')).toHaveTextContent('Sua sessão expirou');
});
it('recupera erro de rede na listagem', async () => {
  let falhar = true;
  buscar.mockImplementation(async (u, o) => {
    if (falhar && String(u).includes('/api/links')) throw new TypeError('offline');
    return api(u, o);
  });
  await abrir();
  expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível conectar');
  falhar = false;
  fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
  expect(await screen.findByRole('heading', { name: 'Campanha' })).toBeVisible();
});
it('pagina pela API com limite fixo e sem misturar páginas', async () => {
  itens = Array.from({ length: 11 }, (_, i) => ({
    ...exemplo,
    id: `22222222-2222-4222-8222-${String(i).padStart(12, '0')}`,
    nome: `Campanha ${i}`,
  }));
  await abrir();
  await screen.findByRole('heading', { name: 'Campanha 0' });
  fireEvent.click(screen.getByRole('button', { name: 'Próxima' }));
  expect(await screen.findByRole('heading', { name: 'Campanha 10' })).toBeVisible();
  expect(screen.queryByRole('heading', { name: 'Campanha 0' })).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Próxima' })).toBeDisabled();
});
it('impede salvar duas vezes durante carregamento', async () => {
  let concluir!: (r: Response) => void;
  buscar.mockImplementation(async (u, o) =>
    o?.method === 'POST'
      ? new Promise<Response>((r) => {
          concluir = r;
        })
      : api(u, o),
  );
  await abrir();
  fireEvent.click(await screen.findByRole('button', { name: 'Criar link' }));
  preencher();
  const form = screen.getByRole('form', { name: 'Criar link' });
  fireEvent.submit(form);
  fireEvent.submit(form);
  expect(screen.getByRole('button', { name: 'Salvando…' })).toBeDisabled();
  expect(escritas()).toHaveLength(1);
  await act(async () => concluir(resposta(201, exemplo)));
});
it('diálogo nomeado, Escape seguro e temas preservados', async () => {
  await abrir();
  fireEvent.click(await screen.findByRole('button', { name: 'Criar link' }));
  const dialogo = screen.getByRole('dialog', { name: 'Criar link' });
  expect(screen.getByLabelText('Nome interno')).toHaveFocus();
  fireEvent(dialogo, new Event('cancel', { cancelable: true }));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Ativar tema escuro' }));
  expect(document.documentElement.dataset.tema).toBe('escuro');
  fireEvent.click(screen.getByRole('button', { name: 'Ativar tema claro' }));
  expect(document.documentElement.dataset.tema).toBe('claro');
});
