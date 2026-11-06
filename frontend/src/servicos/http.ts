export type ErrosCampos = Partial<Record<'nome' | 'email' | 'senha' | 'codigo', string>>;

export class ErroHTTP extends Error {
  constructor(
    public readonly status: number,
    mensagem: string,
    public readonly campos: ErrosCampos = {},
    public readonly aguardarSegundos?: number,
  ) {
    super(mensagem);
  }
}

const urlConfigurada = import.meta.env.VITE_URL_API || 'http://localhost:8000';
const urlAPI = urlConfigurada.replace(/\/+$/, '');

export async function requisitar(
  caminho: string,
  statusEsperado: number,
  opcoes: RequestInit = {},
): Promise<unknown> {
  const controlador = new AbortController();
  const prazo = window.setTimeout(() => controlador.abort(), 15000);
  try {
    const resposta = await fetch(`${urlAPI}${caminho}`, {
      ...opcoes,
      credentials: 'include',
      cache: 'no-store',
      signal: controlador.signal,
      headers: {
        ...(opcoes.body ? { 'Content-Type': 'application/json' } : {}),
        ...opcoes.headers,
      },
    });
    if (!resposta.ok) {
      const dados = await resposta.json().catch(() => null);
      const campos: ErrosCampos = {};
      if (Array.isArray(dados?.erro?.campos)) {
        for (const detalhe of dados.erro.campos) {
          if (
            ['nome', 'email', 'senha', 'codigo'].includes(detalhe?.campo) &&
            typeof detalhe.mensagem === 'string'
          ) {
            campos[detalhe.campo as keyof ErrosCampos] = detalhe.mensagem;
          }
        }
      }
      const mensagens: Record<number, string> = {
        401: 'E-mail ou senha inválidos.',
        403: 'Não foi possível validar a solicitação. Atualize a sessão e tente novamente.',
        413: 'Os dados enviados excedem o tamanho permitido.',
        422: 'Revise os dados informados.',
        429: 'Muitas tentativas. Aguarde antes de tentar novamente.',
        503: 'O serviço está indisponível. Tente novamente em instantes.',
      };
      throw new ErroHTTP(
        resposta.status,
        mensagens[resposta.status] || 'Não foi possível concluir a solicitação.',
        campos,
        obterEspera(resposta.headers.get('Retry-After')),
      );
    }
    if (resposta.status !== statusEsperado)
      throw new Error('Resposta inesperada da API. Tente novamente.');
    return resposta.status === 204 ? undefined : await resposta.json();
  } catch (erro) {
    if (erro instanceof ErroHTTP) throw erro;
    if (erro instanceof TypeError || controlador.signal.aborted) {
      throw new Error('Não foi possível conectar à API. Verifique sua conexão e tente novamente.');
    }
    throw new Error('Resposta inesperada da API. Tente novamente.');
  } finally {
    window.clearTimeout(prazo);
  }
}

function obterEspera(valor: string | null): number | undefined {
  if (!valor) return undefined;
  const segundos = /^\d+$/.test(valor) ? Number(valor) : (Date.parse(valor) - Date.now()) / 1000;
  return Number.isFinite(segundos) ? Math.max(0, Math.ceil(segundos)) : undefined;
}
