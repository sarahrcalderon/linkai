import { useEffect, useState } from 'react';
import { usarAutenticacao } from '../autenticacao/usarAutenticacao';
import { ErroHTTP } from '../../servicos/http';
import { servicoEstatisticas, type Estatisticas, type Periodo, type Resumo } from './servico';

type Resultado = { chave: string; dados?: Estatisticas | Resumo; erro?: string };
function useEstatisticas(dias: Periodo, id?: string) {
  const { executarAutenticado } = usarAutenticacao();
  const [revisao, definirRevisao] = useState(0);
  const chave = `${id || 'resumo'}:${dias}:${revisao}`;
  const [resultado, definirResultado] = useState<Resultado | null>(null);
  useEffect(() => {
    let ativo = true;
    // Adiar um microtask evita a duplicação pelo ciclo de efeitos do StrictMode.
    void Promise.resolve().then(async () => {
      if (!ativo) return;
      try {
        const dados = await executarAutenticado(() =>
          id ? servicoEstatisticas.porLink(id, dias) : servicoEstatisticas.resumo(dias),
        );
        if (ativo) definirResultado({ chave, dados });
      } catch (falha) {
        if (ativo)
          definirResultado({
            chave,
            erro:
              falha instanceof ErroHTTP && [403, 404].includes(falha.status)
                ? 'Link indisponível. Volte à visão geral ou atualize seus links.'
                : falha instanceof Error
                  ? falha.message
                  : 'Não foi possível carregar as estatísticas.',
          });
      }
    });
    return () => {
      ativo = false;
    };
  }, [chave, dias, id, executarAutenticado]);
  return {
    dados: resultado?.chave === chave ? resultado.dados : undefined,
    erro: resultado?.chave === chave ? resultado.erro : undefined,
    carregando: resultado?.chave !== chave,
    recarregar: () => definirRevisao((valor) => valor + 1),
  };
}
export const usarEstatisticas = useEstatisticas;
