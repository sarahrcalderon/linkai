import { requisitar } from '../../servicos/http';

export type Periodo = 7 | 30 | 90;
export type DiaAcessos = { data: string; acessos: number };
export type Estatisticas = {
  total_acessos: number;
  data_inicial: string;
  data_final: string;
  serie_diaria: DiaAcessos[];
};
export type Resumo = Estatisticas & { links_ativos: number; links_inativos: number };
const inteiro = (valor: unknown): valor is number =>
  Number.isSafeInteger(valor) && Number(valor) >= 0;

function ler(dados: unknown, dias: Periodo): Estatisticas {
  const valor = dados as Estatisticas | null;
  if (
    !valor ||
    !inteiro(valor.total_acessos) ||
    typeof valor.data_inicial !== 'string' ||
    typeof valor.data_final !== 'string' ||
    !Number.isFinite(Date.parse(valor.data_inicial)) ||
    !Number.isFinite(Date.parse(valor.data_final)) ||
    !/(Z|\+00:00)$/.test(valor.data_inicial) ||
    !/(Z|\+00:00)$/.test(valor.data_final) ||
    Date.parse(valor.data_final) < Date.parse(valor.data_inicial) ||
    !Array.isArray(valor.serie_diaria) ||
    valor.serie_diaria.length !== dias ||
    !valor.serie_diaria.every(
      (dia, i) =>
        dia &&
        /^\d{4}-\d{2}-\d{2}$/.test(dia.data) &&
        dia.data ===
          new Date(Date.parse(valor.data_inicial) + i * 86400000).toISOString().slice(0, 10) &&
        inteiro(dia.acessos),
    )
  )
    throw new Error('Resposta de estatísticas inválida. Tente novamente.');
  return {
    total_acessos: valor.total_acessos,
    data_inicial: valor.data_inicial,
    data_final: valor.data_final,
    serie_diaria: valor.serie_diaria.map(({ data, acessos }) => ({ data, acessos })),
  };
}
export const servicoEstatisticas = {
  async resumo(dias: Periodo): Promise<Resumo> {
    const dados = (await requisitar(`/api/estatisticas/resumo?dias=${dias}`, 200)) as Resumo;
    const periodo = ler(dados, dias);
    if (!inteiro(dados.links_ativos) || !inteiro(dados.links_inativos))
      throw new Error('Resposta de estatísticas inválida. Tente novamente.');
    return { ...periodo, links_ativos: dados.links_ativos, links_inativos: dados.links_inativos };
  },
  async porLink(id: string, dias: Periodo): Promise<Estatisticas> {
    const dados = (await requisitar(
      `/api/links/${encodeURIComponent(id)}/estatisticas?dias=${dias}`,
      200,
    )) as Estatisticas & { link_id: string };
    const periodo = ler(dados, dias);
    if (dados.link_id !== id)
      throw new Error('Resposta de estatísticas inválida. Tente novamente.');
    return periodo;
  },
};
export const formatarDia = (data: string) =>
  new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    timeZone: 'UTC',
  }).format(new Date(`${data}T00:00:00Z`));
