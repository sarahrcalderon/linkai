import { useCallback, useEffect, useRef, useState } from 'react';
import { usarAutenticacao } from '../autenticacao/usarAutenticacao';
import { servicoLinks, type ListaLinks } from './servico';

function useLinks() {
  const { executarAutenticado } = usarAutenticacao();
  const [pagina, definirPagina] = useState(1);
  const [revisao, definirRevisao] = useState(0);
  const [dados, definirDados] = useState<ListaLinks | null>(null);
  const [carregando, definirCarregando] = useState(true);
  const [erro, definirErro] = useState('');
  const versao = useRef(0);
  useEffect(() => {
    const atual = ++versao.current;
    let ativo = true;
    definirCarregando(true);
    definirErro('');
    void executarAutenticado(() => servicoLinks.listar(pagina))
      .then((resultado) => {
        if (!ativo || atual !== versao.current) return;
        const ultima = Math.max(1, Math.ceil(resultado.total / resultado.tamanho));
        if (pagina > ultima) definirPagina(ultima);
        else definirDados(resultado);
      })
      .catch((falha) => {
        if (ativo && atual === versao.current)
          definirErro(
            falha instanceof Error ? falha.message : 'Não foi possível carregar os links.',
          );
      })
      .finally(() => {
        if (ativo && atual === versao.current) definirCarregando(false);
      });
    return () => {
      ativo = false;
    };
  }, [pagina, revisao, executarAutenticado]);
  const recarregar = useCallback(() => definirRevisao((r) => r + 1), []);
  return { dados, carregando, erro, pagina, definirPagina, recarregar, executarAutenticado };
}
export const usarLinks = useLinks;
