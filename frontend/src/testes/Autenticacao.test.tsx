import { StrictMode } from 'react';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Aplicacao } from '../Aplicacao';

const sessao = {
  usuario: {
    id: '11111111-1111-4111-8111-111111111111',
    nome: 'Ana',
    email: 'ana@example.com',
    email_verificado: true,
  },
  csrf: 'a'.repeat(64),
};
const mensagemCadastro =
  'Solicitação recebida. A verificação de e-mail será necessária para acessar a conta.';
const resposta = (status: number, dados?: unknown) =>
  new Response(dados === undefined ? null : JSON.stringify(dados), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
const erro = (status: number) =>
  resposta(status, { erro: { codigo: 'erro_controlado', mensagem: 'Mensagem controlada' } });
const buscar = vi.fn<typeof fetch>();

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  document.documentElement.dataset.tema = 'claro';
  buscar.mockReset();
  buscar.mockImplementation(async (url) => {
    if (String(url).endsWith('/api/usuarios/me')) return erro(401);
    throw new Error(`Requisição não prevista no teste: ${url}`);
  });
  vi.stubGlobal('fetch', buscar);
});
afterEach(() => {
  vi.unstubAllGlobals();
  window.history.replaceState(null, '', '/');
});

async function abrir(caminho: string) {
  window.history.replaceState(null, '', caminho);
  await act(async () => {
    render(
      <StrictMode>
        <Aplicacao />
      </StrictMode>,
    );
  });
}
function preencher(cadastro = false) {
  if (cadastro)
    fireEvent.change(screen.getByLabelText('Nome'), { target: { value: ' Ana Silva ' } });
  fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: ' ANA@EXAMPLE.COM ' } });
  fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'Frase longa de teste!' } });
}
const chamadas = (trecho: string) =>
  buscar.mock.calls.filter(([url]) => String(url).endsWith(trecho));

describe('Cadastro integrado', () => {
  it('envia dados normalizados, aceita 202 e não autentica nem afirma envio de e-mail', async () => {
    buscar.mockImplementation(async (url) =>
      String(url).endsWith('/cadastro') ? resposta(202, { mensagem: mensagemCadastro }) : erro(401),
    );
    await abrir('/cadastro');
    preencher(true);
    fireEvent.submit(screen.getByRole('form', { name: 'Cadastro' }));
    expect(await screen.findByRole('status')).toHaveTextContent(mensagemCadastro);
    const opcoes = chamadas('/cadastro')[0][1];
    expect(opcoes?.credentials).toBe('include');
    expect(JSON.parse(String(opcoes?.body))).toEqual({
      nome: 'Ana Silva',
      email: 'ana@example.com',
      senha: 'Frase longa de teste!',
    });
    expect(chamadas('/login')).toHaveLength(0);
    expect(screen.queryByText('Sua conta está conectada ao Linkai.')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Senha')).toHaveValue('');
  });

  it('valida campos com rótulos, associação de erros e foco', async () => {
    await abrir('/cadastro');
    fireEvent.submit(screen.getByRole('form', { name: 'Cadastro' }));
    for (const rotulo of ['Nome', 'E-mail', 'Senha']) {
      expect(screen.getByLabelText(rotulo)).toHaveAttribute('aria-invalid', 'true');
      expect(screen.getByLabelText(rotulo)).toHaveAccessibleDescription();
    }
    expect(screen.getByLabelText('Nome')).toHaveFocus();
    expect(chamadas('/cadastro')).toHaveLength(0);
  });

  it('impede envios simultâneos e exibe carregamento', async () => {
    let concluir!: (resposta: Response) => void;
    buscar.mockImplementation(async (url) =>
      String(url).endsWith('/cadastro')
        ? new Promise<Response>((resolver) => {
            concluir = resolver;
          })
        : erro(401),
    );
    await abrir('/cadastro');
    preencher(true);
    const formulario = screen.getByRole('form', { name: 'Cadastro' });
    fireEvent.submit(formulario);
    fireEvent.submit(formulario);
    expect(screen.getByRole('button', { name: 'Enviando…' })).toBeDisabled();
    expect(formulario).toHaveAttribute('aria-busy', 'true');
    expect(chamadas('/cadastro')).toHaveLength(1);
    await act(async () => concluir(resposta(202, { mensagem: mensagemCadastro })));
    expect(await screen.findByRole('status')).toHaveTextContent(mensagemCadastro);
  });

  it('trata falha de rede sem simular sucesso', async () => {
    buscar.mockImplementation(async (url) => {
      if (String(url).endsWith('/cadastro')) throw new TypeError('offline');
      return erro(401);
    });
    await abrir('/cadastro');
    preencher(true);
    fireEvent.submit(screen.getByRole('form', { name: 'Cadastro' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível conectar à API');
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Criar conta' })).toBeEnabled();
  });

  it('exibe erros de campos recebidos da API', async () => {
    buscar.mockImplementation(async (url) =>
      String(url).endsWith('/cadastro')
        ? resposta(422, {
            erro: {
              codigo: 'dados_invalidos',
              mensagem: 'Revise os dados informados.',
              campos: [
                { campo: 'email', mensagem: 'Informe um e-mail válido com até 254 caracteres.' },
              ],
            },
          })
        : erro(401),
    );
    await abrir('/cadastro');
    preencher(true);
    fireEvent.submit(screen.getByRole('form', { name: 'Cadastro' }));
    expect(
      await screen.findByText('Informe um e-mail válido com até 254 caracteres.'),
    ).toBeInTheDocument();
    expect(screen.getByLabelText('E-mail')).toHaveAttribute('aria-invalid', 'true');
  });
});

describe('Login e sessão', () => {
  it('autentica com API real no contrato e redireciona à área privada', async () => {
    buscar.mockImplementation(async (url) =>
      String(url).endsWith('/login') ? resposta(200, sessao) : erro(401),
    );
    await abrir('/login');
    preencher();
    fireEvent.submit(screen.getByRole('form', { name: 'Login' }));
    expect(await screen.findByRole('heading', { name: 'Olá, Ana.' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/dashboard');
    expect(localStorage.getItem('csrf')).toBeNull();
    expect(localStorage.length).toBe(1);
    expect(localStorage.key(0)).toBe('tema');
    expect(sessionStorage.length).toBe(0);
  });

  it.each(['credenciais inválidas', 'conta não verificada'])(
    'mantém login bloqueado para %s',
    async () => {
      buscar.mockResolvedValue(erro(401));
      await abrir('/login');
      preencher();
      fireEvent.submit(screen.getByRole('form', { name: 'Login' }));
      expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou senha inválidos.');
      expect(window.location.pathname).toBe('/login');
      expect(screen.queryByText('Sua conta está conectada ao Linkai.')).not.toBeInTheDocument();
    },
  );

  it('rejeita resposta 200 com usuário não verificado', async () => {
    buscar.mockImplementation(async (url) =>
      String(url).endsWith('/login')
        ? resposta(200, { ...sessao, usuario: { ...sessao.usuario, email_verificado: false } })
        : erro(401),
    );
    await abrir('/login');
    preencher();
    fireEvent.submit(screen.getByRole('form', { name: 'Login' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Não foi possível confirmar a autenticação',
    );
    expect(window.location.pathname).toBe('/login');
  });

  it('trata limite de tentativas', async () => {
    buscar.mockImplementation(async (url) =>
      String(url).endsWith('/login') ? erro(429) : erro(401),
    );
    await abrir('/login');
    preencher();
    fireEvent.submit(screen.getByRole('form', { name: 'Login' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Muitas tentativas');
  });

  it('consulta a sessão uma vez mesmo no StrictMode e preserva o tema', async () => {
    buscar.mockResolvedValue(resposta(200, sessao));
    await abrir('/dashboard');
    expect(await screen.findByRole('heading', { name: 'Olá, Ana.' })).toBeInTheDocument();
    expect(chamadas('/api/usuarios/me')).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Ativar tema escuro' }));
    expect(document.documentElement.dataset.tema).toBe('escuro');
    expect(chamadas('/api/usuarios/me')).toHaveLength(1);
  });

  it('não mostra área privada durante a consulta e redireciona visitante', async () => {
    let concluir!: (resposta: Response) => void;
    buscar.mockImplementation(
      () =>
        new Promise<Response>((resolver) => {
          concluir = resolver;
        }),
    );
    await abrir('/dashboard');
    expect(screen.getByRole('status')).toHaveTextContent('Carregando');
    expect(screen.queryByText('Sua conta está conectada ao Linkai.')).not.toBeInTheDocument();
    await act(async () => concluir(erro(401)));
    expect(await screen.findByRole('form', { name: 'Login' })).toBeInTheDocument();
    expect(window.location.pathname).toBe('/login');
  });

  it('distingue indisponibilidade de ausência de sessão e permite repetir', async () => {
    buscar
      .mockRejectedValueOnce(new TypeError('offline'))
      .mockImplementation(async () => erro(401));
    await abrir('/dashboard');
    expect(await screen.findByRole('alert')).toHaveTextContent('Não foi possível conectar');
    expect(window.location.pathname).toBe('/dashboard');
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    expect(await screen.findByRole('form', { name: 'Login' })).toBeInTheDocument();
  });

  it('remove área privada quando /me informa expiração', async () => {
    buscar.mockResolvedValueOnce(resposta(200, sessao)).mockImplementation(async () => erro(401));
    await abrir('/dashboard');
    fireEvent.click(await screen.findByRole('button', { name: 'Atualizar sessão' }));
    expect(await screen.findByRole('form', { name: 'Login' })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('Sua sessão expirou');
  });

  it('envia CSRF e cookies no logout e limpa a sessão após 204', async () => {
    buscar.mockImplementation(async (url) =>
      String(url).endsWith('/logout') ? resposta(204) : resposta(200, sessao),
    );
    await abrir('/dashboard');
    fireEvent.click(await screen.findByRole('button', { name: 'Sair' }));
    expect(await screen.findByRole('form', { name: 'Login' })).toBeInTheDocument();
    const opcoes = chamadas('/logout')[0][1];
    expect(opcoes?.credentials).toBe('include');
    expect(opcoes?.headers).toMatchObject({ 'X-CSRF-Token': sessao.csrf });
    expect(chamadas('/api/usuarios/me')).toHaveLength(1);
  });

  it('preserva sessão quando a API rejeita o logout', async () => {
    buscar.mockImplementation(async (url) =>
      String(url).endsWith('/logout') ? erro(503) : resposta(200, sessao),
    );
    await abrir('/dashboard');
    fireEvent.click(await screen.findByRole('button', { name: 'Sair' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('O serviço está indisponível');
    expect(screen.getByRole('heading', { name: 'Olá, Ana.' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Sair' })).toBeEnabled());
  });
});
