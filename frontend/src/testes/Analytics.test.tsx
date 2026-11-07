import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { Analytics } from '../funcionalidades/estatisticas/Analytics';
import { servicoEstatisticas, formatarDia } from '../funcionalidades/estatisticas/servico';
import { ErroHTTP } from '../servicos/http';

const executar = vi.fn(async <T,>(acao: () => Promise<T>) => acao());
vi.mock('../funcionalidades/autenticacao/usarAutenticacao', () => ({
  usarAutenticacao: () => ({ executarAutenticado: executar }),
}));
const buscar = vi.fn<typeof fetch>();
function dados(dias = 7, total = 12) {
  return {
    total_acessos: total,
    links_ativos: 2,
    links_inativos: 1,
    data_inicial: '2026-01-01T00:00:00Z',
    data_final: new Date(Date.UTC(2026, 0, dias, 12)).toISOString(),
    serie_diaria: Array.from({ length: dias }, (_, i) => ({
      data: new Date(Date.UTC(2026, 0, i + 1)).toISOString().slice(0, 10),
      acessos: i === 0 ? total : 0,
    })),
  };
}
beforeEach(() => {
  executar.mockClear();
  buscar.mockReset().mockImplementation(async (url) => {
    const endereco = new URL(String(url));
    const dias = Number(endereco.searchParams.get('dias'));
    return new Response(JSON.stringify({ ...dados(dias), link_id: 'id-link' }), { status: 200 });
  });
  vi.stubGlobal('fetch', buscar);
});
afterEach(() => vi.unstubAllGlobals());
const abrir = () =>
  render(
    <StrictMode>
      <Analytics link={null} voltar={vi.fn()} />
    </StrictMode>,
  );

it('renderiza totais da API, explicação e apenas uma requisição em StrictMode', async () => {
  abrir();
  expect(await screen.findByText('12', { selector: 'article p' })).toBeVisible();
  expect(screen.getByText('Links ativos')).toBeVisible();
  expect(screen.getByText('Links inativos')).toBeVisible();
  expect(screen.getByText(/não visitantes únicos/)).toBeVisible();
  expect(buscar).toHaveBeenCalledTimes(1);
  expect(buscar.mock.calls[0][1]).toMatchObject({ credentials: 'include', cache: 'no-store' });
});
it('exibe carregamento sem indicadores fictícios', async () => {
  buscar.mockImplementation(() => new Promise(() => {}));
  abrir();
  expect(screen.getByRole('status')).toHaveTextContent('Carregando');
  expect(screen.queryByText('Links ativos')).not.toBeInTheDocument();
});
it('exibe zeros e orienta a criação quando não há links', async () => {
  buscar.mockResolvedValue(
    new Response(JSON.stringify({ ...dados(7, 0), links_ativos: 0, links_inativos: 0 })),
  );
  abrir();
  expect(await screen.findByText('Nenhum acesso registrado neste período.')).toBeVisible();
  expect(screen.getByText(/Crie seu primeiro link/)).toBeVisible();
  fireEvent.click(screen.getByText('Ver tabela diária'));
  expect(screen.getByRole('table')).toBeVisible();
  expect(screen.getAllByRole('row')).toHaveLength(8);
});
it.each([30, 90])(
  'consulta %i dias e remove a série anterior durante o carregamento',
  async (dias) => {
    abrir();
    await screen.findByText('12', { selector: 'article p' });
    fireEvent.change(screen.getByLabelText('Período'), { target: { value: String(dias) } });
    expect(screen.queryByText('12', { selector: 'article p' })).not.toBeInTheDocument();
    expect(
      await screen.findByText(`Últimos ${dias} dias · UTC · Até`, { exact: false }),
    ).toBeVisible();
    expect(String(buscar.mock.calls.at(-1)?.[0])).toContain(`dias=${dias}`);
  },
);
it('descarta respostas atrasadas após alternância rápida', async () => {
  let concluir!: (resposta: Response) => void;
  buscar.mockImplementation((url) => {
    const dias = Number(new URL(String(url)).searchParams.get('dias'));
    if (dias === 30)
      return new Promise((resolver) => {
        concluir = resolver;
      });
    return Promise.resolve(new Response(JSON.stringify(dados(dias, dias))));
  });
  abrir();
  await screen.findByText('7', { selector: 'article p' });
  fireEvent.change(screen.getByLabelText('Período'), { target: { value: '30' } });
  await waitFor(() => expect(concluir).toBeTypeOf('function'));
  fireEvent.change(screen.getByLabelText('Período'), { target: { value: '90' } });
  expect(await screen.findByText('90', { selector: 'article p' })).toBeVisible();
  await act(async () => concluir(new Response(JSON.stringify(dados(30, 30)))));
  expect(screen.queryByText('30', { selector: 'article p' })).not.toBeInTheDocument();
  expect(screen.getByText('90', { selector: 'article p' })).toBeVisible();
});
it('consulta somente o link selecionado e exibe sua URL e nome', async () => {
  const voltar = vi.fn();
  render(
    <Analytics
      link={{
        id: 'id-link',
        nome: 'Campanha',
        slug: 'campanha',
        ativo: false,
        mensagem: null,
        numero_whatsapp: '+5511999999999',
        criado_em: '',
        atualizado_em: '',
      }}
      voltar={voltar}
    />,
  );
  expect(await screen.findByText('12', { selector: 'article p' })).toBeVisible();
  expect(screen.getByRole('heading', { name: 'Estatísticas de Campanha' })).toBeVisible();
  expect(screen.getByText(/\/r\/campanha$/)).toBeVisible();
  expect(screen.queryByText('Links ativos')).not.toBeInTheDocument();
  expect(String(buscar.mock.calls[0][0])).toContain('/api/links/id-link/estatisticas?dias=7');
  fireEvent.click(screen.getByText('Voltar à visão geral'));
  expect(voltar).toHaveBeenCalledOnce();
});
it.each([403, 404])(
  'trata link inexistente ou não autorizado (%i) sem dados anteriores',
  async (status) => {
    buscar.mockResolvedValue(new Response('{}', { status }));
    abrir();
    expect(await screen.findByRole('alert')).toHaveTextContent('Link indisponível');
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
  },
);
it('trata erro de rede e permite tentar novamente', async () => {
  buscar.mockRejectedValueOnce(new TypeError('Failed to fetch'));
  abrir();
  expect(await screen.findByRole('alert')).toHaveTextContent('Verifique sua conexão');
  fireEvent.click(screen.getByText('Tentar novamente'));
  expect(await screen.findByText('12', { selector: 'article p' })).toBeVisible();
});
it('entrega 401 ao mecanismo de sessão existente', async () => {
  buscar.mockResolvedValue(new Response('{}', { status: 401 }));
  await expect(servicoEstatisticas.resumo(7)).rejects.toBeInstanceOf(ErroHTTP);
});
it('oferece consulta por teclado, detalhe acessível e tabela completa em UTC', async () => {
  abrir();
  const controle = await screen.findByRole('slider', { name: 'Consultar dia do gráfico' });
  expect(screen.getByRole('img')).toHaveAccessibleName(/Valores na tabela/);
  fireEvent.change(controle, { target: { value: '1' } });
  expect(controle).toHaveAttribute('aria-valuetext', '02/01: 0 acessos');
  expect(screen.getByText('02/01: 0 acessos registrados')).toBeVisible();
  expect(screen.getByRole('tooltip')).toHaveTextContent('02/01: 0 acessos registrados');
  fireEvent.click(screen.getByText('Ver tabela diária'));
  expect(screen.getByRole('rowheader', { name: '01/01/2026' })).toBeVisible();
  expect(formatarDia('2026-01-01')).toBe('01/01');
});
it('rejeita respostas incompletas sem fabricar estatísticas', async () => {
  buscar.mockResolvedValue(new Response(JSON.stringify({ ...dados(), serie_diaria: [] })));
  abrir();
  expect(await screen.findByRole('alert')).toHaveTextContent('Resposta de estatísticas inválida');
  expect(screen.queryByText('12', { selector: 'article p' })).not.toBeInTheDocument();
});
