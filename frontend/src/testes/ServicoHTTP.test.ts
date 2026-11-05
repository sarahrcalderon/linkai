import { afterEach, describe, expect, it, vi } from 'vitest';
import { requisitar } from '../servicos/http';
import { servicoAutenticacao } from '../funcionalidades/autenticacao/servico';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('Serviço HTTP', () => {
  it('não aceita outro 2xx como confirmação de cadastro 202', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () => new Response(JSON.stringify({ mensagem: 'não confirmar' }), { status: 201 }),
      ),
    );
    await expect(
      servicoAutenticacao.cadastrar({
        nome: 'Ana',
        email: 'ana@example.com',
        senha: 'Frase longa de teste!',
      }),
    ).rejects.toThrow('Resposta inesperada');
  });

  it('não interpreta corpo inválido como autenticação', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('não é JSON', { status: 200 })),
    );
    await expect(servicoAutenticacao.consultar()).rejects.toThrow('Resposta inesperada');
  });

  it('aborta requisição sem resposta em 15 segundos e apresenta falha de rede', async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url, opcoes: RequestInit) =>
          new Promise((_resolver, rejeitar) => {
            opcoes.signal?.addEventListener('abort', () =>
              rejeitar(new DOMException('Tempo esgotado', 'AbortError')),
            );
          }),
      ),
    );
    const requisicao = requisitar('/api/usuarios/me', 200).catch((erro: unknown) => erro);
    await vi.advanceTimersByTimeAsync(15001);
    expect(await requisicao).toBeInstanceOf(Error);
    expect(String(await requisicao)).toContain('Não foi possível conectar à API');
  });
});
