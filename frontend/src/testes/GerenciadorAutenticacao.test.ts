import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { GerenciadorAutenticacao } from '../funcionalidades/autenticacao/gerenciador';

const sessao = {
  usuario: {
    id: '11111111-1111-4111-8111-111111111111',
    nome: 'Ana',
    email: 'ana@example.com',
    email_verificado: true,
  },
  csrf: 'b'.repeat(64),
};
const responder = (status: number, dados?: unknown) =>
  new Response(dados === undefined ? null : JSON.stringify(dados), { status });
const buscar = vi.fn<typeof fetch>();
beforeEach(() => {
  buscar.mockReset();
  vi.stubGlobal('fetch', buscar);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('Ciclo da autenticação', () => {
  it('ignora uma consulta antiga concluída depois do logout', async () => {
    let concluir!: (resposta: Response) => void;
    let consultas = 0;
    buscar.mockImplementation(async (url) => {
      if (String(url).endsWith('/logout')) return responder(204);
      if (++consultas === 1) return responder(200, sessao);
      return new Promise<Response>((resolver) => {
        concluir = resolver;
      });
    });
    const gerenciador = new GerenciadorAutenticacao();
    await gerenciador.iniciar();
    const pendente = gerenciador.revalidar(true);
    await gerenciador.sair();
    concluir(responder(200, sessao));
    await pendente;
    expect(gerenciador.obterEstado().situacao).toBe('nao_autenticado');
    expect(gerenciador.obterEstado().usuario).toBeNull();
  });

  it('não consulta nem duplica mutações durante logout pendente', async () => {
    let concluir!: (resposta: Response) => void;
    buscar.mockImplementation(async (url) =>
      String(url).endsWith('/logout')
        ? new Promise<Response>((resolver) => {
            concluir = resolver;
          })
        : responder(200, sessao),
    );
    const gerenciador = new GerenciadorAutenticacao();
    await gerenciador.iniciar();
    const saida = gerenciador.sair();
    await gerenciador.revalidar(true);
    await expect(gerenciador.sair()).rejects.toThrow('Aguarde a operação');
    expect(buscar).toHaveBeenCalledTimes(2);
    concluir(responder(204));
    await saida;
    expect(gerenciador.obterEstado().usuario).toBeNull();
  });

  it('não deixa uma inicialização tardia desfazer o login', async () => {
    let concluir!: (resposta: Response) => void;
    buscar.mockImplementation(async (url) =>
      String(url).endsWith('/login')
        ? responder(200, sessao)
        : new Promise<Response>((resolver) => {
            concluir = resolver;
          }),
    );
    const gerenciador = new GerenciadorAutenticacao();
    const inicializacao = gerenciador.iniciar();
    await gerenciador.entrar({ email: 'ana@example.com', senha: 'Frase longa de teste!' });
    concluir(
      responder(401, { erro: { codigo: 'sessao_invalida', mensagem: 'Autenticação necessária.' } }),
    );
    await inicializacao;
    expect(gerenciador.obterEstado().situacao).toBe('autenticado');
  });

  it('não fica carregando quando login rejeitado se sobrepõe à inicialização', async () => {
    let concluir!: (resposta: Response) => void;
    buscar.mockImplementation(async (url) =>
      String(url).endsWith('/login')
        ? responder(401)
        : new Promise<Response>((resolver) => {
            concluir = resolver;
          }),
    );
    const gerenciador = new GerenciadorAutenticacao();
    const inicializacao = gerenciador.iniciar();
    await expect(
      gerenciador.entrar({ email: 'ana@example.com', senha: 'incorreta' }),
    ).rejects.toThrow();
    concluir(responder(401));
    await inicializacao;
    expect(gerenciador.obterEstado().situacao).toBe('nao_autenticado');
  });

  it('deduplica e limita consultas por retorno de foco', async () => {
    let agora = 100000;
    vi.spyOn(Date, 'now').mockImplementation(() => agora);
    buscar.mockImplementation(async () => responder(200, sessao));
    const gerenciador = new GerenciadorAutenticacao();
    await Promise.all([gerenciador.iniciar(), gerenciador.iniciar()]);
    await gerenciador.revalidar();
    expect(buscar).toHaveBeenCalledTimes(1);
    agora += 61000;
    await Promise.all([gerenciador.revalidar(), gerenciador.revalidar()]);
    expect(buscar).toHaveBeenCalledTimes(2);
  });
});
