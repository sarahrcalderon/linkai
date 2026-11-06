import { ErroHTTP, requisitar } from '../../servicos/http';

export type DadosLink = {
  nome: string;
  slug: string;
  numero_whatsapp: string;
  mensagem: string | null;
};
export type LinkPersonalizado = DadosLink & {
  id: string;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string;
};
export type AlteracoesLink = Partial<DadosLink & { ativo: boolean }>;
export type ListaLinks = {
  itens: LinkPersonalizado[];
  total: number;
  pagina: number;
  tamanho: number;
};

function lerLink(dados: unknown): LinkPersonalizado {
  const link = dados as LinkPersonalizado | null;
  if (
    !link ||
    typeof link !== 'object' ||
    !/^[a-f0-9-]{36}$/i.test(link.id) ||
    !['nome', 'slug', 'numero_whatsapp', 'criado_em', 'atualizado_em'].every(
      (c) => typeof (link as Record<string, unknown>)[c] === 'string',
    ) ||
    typeof link.ativo !== 'boolean' ||
    !(link.mensagem === null || typeof link.mensagem === 'string')
  ) {
    throw new Error('Resposta de links inválida. Tente novamente.');
  }
  return {
    id: link.id,
    nome: link.nome,
    slug: link.slug,
    numero_whatsapp: link.numero_whatsapp,
    mensagem: link.mensagem,
    ativo: link.ativo,
    criado_em: link.criado_em,
    atualizado_em: link.atualizado_em,
  };
}

async function escrever(
  caminho: string,
  status: number,
  metodo: string,
  csrf: string,
  dados?: AlteracoesLink,
) {
  try {
    return await requisitar(caminho, status, {
      method: metodo,
      headers: { 'X-CSRF-Token': csrf },
      ...(dados ? { body: JSON.stringify(dados) } : {}),
    });
  } catch (erro) {
    if (erro instanceof ErroHTTP && erro.status === 409)
      throw new ErroHTTP(409, 'Este slug está indisponível. Escolha outro endereço.');
    if (erro instanceof ErroHTTP && erro.status === 404)
      throw new ErroHTTP(404, 'Link não encontrado. Atualize a lista.');
    throw erro;
  }
}

export const servicoLinks = {
  async listar(pagina: number): Promise<ListaLinks> {
    const dados = (await requisitar(`/api/links?pagina=${pagina}&tamanho=10`, 200)) as ListaLinks;
    if (
      !dados ||
      !Array.isArray(dados.itens) ||
      !Number.isInteger(dados.total) ||
      dados.total < 0 ||
      dados.pagina !== pagina ||
      dados.tamanho !== 10
    )
      throw new Error('Resposta de listagem inválida. Tente novamente.');
    return { ...dados, itens: dados.itens.map(lerLink) };
  },
  async consultar(id: string) {
    return lerLink(await requisitar(`/api/links/${encodeURIComponent(id)}`, 200));
  },
  async criar(dados: DadosLink, csrf: string) {
    return lerLink(await escrever('/api/links', 201, 'POST', csrf, dados));
  },
  async atualizar(id: string, dados: AlteracoesLink, csrf: string) {
    return lerLink(
      await escrever(`/api/links/${encodeURIComponent(id)}`, 200, 'PATCH', csrf, dados),
    );
  },
  async excluir(id: string, csrf: string) {
    await escrever(`/api/links/${encodeURIComponent(id)}`, 204, 'DELETE', csrf);
  },
};

export function urlPublica(slug: string): string {
  const origem = new URL(import.meta.env.VITE_URL_PUBLICA_LINKS || window.location.origin);
  if (!['http:', 'https:'].includes(origem.protocol) || origem.username || origem.password)
    throw new Error('Origem pública de links inválida.');
  return new URL(`/r/${encodeURIComponent(slug)}`, origem).href;
}
