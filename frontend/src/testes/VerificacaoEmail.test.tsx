import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { Aplicacao } from '../Aplicacao';
import { contextoVerificacao } from '../funcionalidades/autenticacao/verificacao';

const buscar = vi.fn<typeof fetch>();
const resposta = (
  status: number,
  dados: unknown = { mensagem: 'Solicitação recebida.' },
  headers = {},
) => new Response(JSON.stringify(dados), { status, headers });
beforeEach(() => {
  contextoVerificacao.email = '';
  contextoVerificacao.reenviarEm = 0;
  localStorage.clear();
  sessionStorage.clear();
  buscar.mockReset();
  buscar.mockImplementation(async () => resposta(401));
  vi.stubGlobal('fetch', buscar);
  window.history.replaceState(null, '', '/verificar-email');
});
afterEach(() => {
  vi.useRealTimers();
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
function preencher(codigo = '123456') {
  fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: ' ANA@EXAMPLE.COM ' } });
  fireEvent.change(screen.getByLabelText('Código de seis dígitos'), { target: { value: codigo } });
}
function enviar() {
  fireEvent.submit(screen.getByRole('form', { name: 'Verificação de e-mail' }));
}
const chamadas = (trecho: string) =>
  buscar.mock.calls.filter(([url]) => String(url).endsWith(trecho));

it('renderiza rota pública com rótulos, campo único e recuperação sem armazenamento', async () => {
  await abrir();
  expect(screen.getByRole('heading', { name: 'Verifique seu e-mail' })).toHaveFocus();
  expect(screen.getByLabelText('E-mail')).toHaveValue('');
  expect(screen.getByLabelText('Código de seis dígitos')).toHaveAttribute(
    'autocomplete',
    'one-time-code',
  );
  expect(screen.getByText(/preencha o endereço novamente/)).toBeVisible();
  expect(window.location.search).toBe('');
});
it.each(['', '12345', 'abcdef', '１２３４５６'])(
  'rejeita formato inválido %s e foca o campo',
  async (codigo) => {
    await abrir();
    preencher(codigo);
    enviar();
    expect(screen.getByLabelText('Código de seis dígitos')).toHaveFocus();
    expect(screen.getByLabelText('Código de seis dígitos')).toHaveAccessibleDescription(
      'Informe os seis dígitos do código.',
    );
    expect(chamadas('/verificar-email')).toHaveLength(0);
  },
);
it('valida o e-mail antes de confirmar ou reenviar', async () => {
  await abrir();
  fireEvent.click(screen.getByRole('button', { name: 'Reenviar código' }));
  expect(screen.getByLabelText('E-mail')).toHaveFocus();
  expect(screen.getByLabelText('E-mail')).toHaveAttribute('aria-invalid', 'true');
  expect(chamadas('/reenviar-codigo')).toHaveLength(0);
});
it('confirma, limpa dados, não autentica e permite ir ao login', async () => {
  buscar.mockImplementation(async (url) =>
    resposta(String(url).endsWith('/verificar-email') ? 200 : 401),
  );
  await abrir();
  preencher();
  enviar();
  expect(
    await screen.findByText('E-mail verificado. Entre na sua conta para continuar.'),
  ).toHaveFocus();
  expect(JSON.parse(String(chamadas('/verificar-email')[0][1]?.body))).toEqual({
    email: 'ana@example.com',
    codigo: '123456',
  });
  expect(screen.queryByLabelText('Código de seis dígitos')).not.toBeInTheDocument();
  expect(chamadas('/login')).toHaveLength(0);
  expect(contextoVerificacao.email).toBe('');
  expect(sessionStorage.length).toBe(0);
  expect(Object.keys(localStorage)).toEqual(['tema']);
  fireEvent.click(screen.getByRole('link', { name: 'Ir para o login' }));
  expect(await screen.findByRole('form', { name: 'Login' })).toBeVisible();
});
it.each(['incorreto', 'expirado', 'utilizado'])(
  'mantém erro neutro para código %s e limpa o código',
  async () => {
    buscar.mockImplementation(async (url) =>
      resposta(String(url).endsWith('/verificar-email') ? 400 : 401),
    );
    await abrir();
    preencher();
    enviar();
    expect(await screen.findByRole('alert')).toHaveTextContent('Código inválido ou indisponível.');
    expect(screen.getByLabelText('Código de seis dígitos')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Confirmar e-mail' })).toBeEnabled();
  },
);
it('reenvia de modo neutro e só libera após o cooldown', async () => {
  buscar.mockImplementation(async (url) =>
    resposta(String(url).endsWith('/reenviar-codigo') ? 202 : 401),
  );
  await abrir();
  preencher();
  vi.useFakeTimers();
  fireEvent.click(screen.getByRole('button', { name: 'Reenviar código' }));
  await act(async () => {});
  expect(screen.getByText(/A entrega pode levar alguns instantes/)).toBeVisible();
  expect(screen.getByRole('button', { name: 'Reenviar código' })).toBeDisabled();
  expect(screen.getByRole('timer')).toHaveTextContent('60 segundos');
  expect(screen.getByRole('timer')).toHaveAttribute('aria-live', 'off');
  await act(async () => vi.advanceTimersByTime(60000));
  expect(screen.getByRole('button', { name: 'Reenviar código' })).toBeEnabled();
  expect(chamadas('/reenviar-codigo')).toHaveLength(1);
});
it.each(['confirmar', 'reenviar'])('bloqueia chamadas concorrentes ao %s', async (acao) => {
  let concluir!: (valor: Response) => void;
  buscar.mockImplementation(async (url) =>
    String(url).endsWith(acao === 'confirmar' ? '/verificar-email' : '/reenviar-codigo')
      ? new Promise<Response>((resolver) => {
          concluir = resolver;
        })
      : resposta(401),
  );
  await abrir();
  preencher();
  if (acao === 'confirmar') {
    enviar();
    enviar();
  } else {
    fireEvent.click(screen.getByRole('button', { name: 'Reenviar código' }));
    enviar();
  }
  expect(screen.getByRole('form')).toHaveAttribute('aria-busy', 'true');
  expect(screen.getByLabelText('E-mail')).toBeDisabled();
  expect(chamadas('/verificar-email').length + chamadas('/reenviar-codigo').length).toBe(1);
  await act(async () => concluir(resposta(acao === 'confirmar' ? 200 : 202)));
});
it.each(['/verificar-email', '/reenviar-codigo'])(
  'recupera falha de rede em %s',
  async (caminho) => {
    buscar.mockImplementation(async (url) => {
      if (String(url).endsWith(caminho)) throw new TypeError('offline');
      return resposta(401);
    });
    await abrir();
    preencher();
    if (caminho === '/verificar-email') enviar();
    else fireEvent.click(screen.getByRole('button', { name: 'Reenviar código' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível conectar à API');
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Confirmar e-mail' })).toBeEnabled(),
    );
  },
);
it('respeita Retry-After disponível sem presumir existência da conta', async () => {
  buscar.mockImplementation(async (url) =>
    resposta(String(url).endsWith('/reenviar-codigo') ? 429 : 401, {}, { 'Retry-After': '120' }),
  );
  await abrir();
  preencher();
  fireEvent.click(screen.getByRole('button', { name: 'Reenviar código' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Muitas tentativas');
  expect(screen.getByRole('timer')).toHaveTextContent('120 segundos');
});
it('preserva temas ao alternar e mantém código fora do armazenamento', async () => {
  await abrir();
  preencher();
  fireEvent.click(screen.getByRole('button', { name: 'Ativar tema escuro' }));
  expect(document.documentElement.dataset.tema).toBe('escuro');
  fireEvent.click(screen.getByRole('button', { name: 'Ativar tema claro' }));
  expect(document.documentElement.dataset.tema).toBe('claro');
  expect(Object.keys(localStorage)).toEqual(['tema']);
  expect(sessionStorage.length).toBe(0);
});
