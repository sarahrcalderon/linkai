import { useEffect } from 'react';
import { LoaderCircle } from 'lucide-react';
import { Botao } from '../componentes/Botao';
import { EstruturaAcesso } from '../componentes/EstruturaAcesso';
import { Feedback } from '../componentes/Feedback';
import { LinkInterno } from '../componentes/LinkInterno';
import { usarAutenticacao } from '../funcionalidades/autenticacao/usarAutenticacao';
import { PaginaInicial } from '../paginas/PaginaInicial';
import { PaginaCadastro } from '../paginas/PaginaCadastro';
import { PaginaLogin } from '../paginas/PaginaLogin';
import { PaginaDashboard } from '../paginas/PaginaDashboard';
import { navegar, usarNavegacao } from './usarNavegacao';

function Redirecionar({ caminho }: { caminho: string }) {
  useEffect(() => {
    navegar(caminho, true);
  }, [caminho]);
  return (
    <p role="status" className="p-6">
      Redirecionando…
    </p>
  );
}

export function RotasAplicacao() {
  const caminho = usarNavegacao();
  const { situacao, mensagem, revalidar } = usarAutenticacao();
  useEffect(() => {
    document.title = `${({ '/login': 'Entrar', '/cadastro': 'Criar conta', '/dashboard': 'Minha conta' } as Record<string, string>)[caminho] || 'Início'} | Linkai`;
    const titulo = document.querySelector<HTMLElement>('main h1');
    if (titulo) {
      titulo.tabIndex = -1;
      titulo.focus();
    }
  }, [caminho]);
  if (caminho === '/dashboard') {
    if (situacao === 'carregando')
      return (
        <EstruturaAcesso
          titulo="Consultando sua sessão"
          descricao="Aguarde a confirmação do seu acesso."
        >
          <p role="status" className="flex items-center gap-2">
            <LoaderCircle className="animate-spin" aria-hidden="true" /> Carregando…
          </p>
        </EstruturaAcesso>
      );
    if (situacao === 'indisponivel')
      return (
        <EstruturaAcesso
          titulo="Não foi possível confirmar seu acesso"
          descricao="Tente novamente para continuar."
        >
          <Feedback mensagem={mensagem || 'API indisponível.'} />
          <Botao className="mt-5" onClick={() => void revalidar(true)}>
            Tentar novamente
          </Botao>
        </EstruturaAcesso>
      );
    return situacao === 'autenticado' ? <PaginaDashboard /> : <Redirecionar caminho="/login" />;
  }
  if (caminho === '/login' || caminho === '/cadastro') {
    if (situacao === 'autenticado') return <Redirecionar caminho="/dashboard" />;
    return caminho === '/login' ? <PaginaLogin /> : <PaginaCadastro />;
  }
  if (caminho === '/') return <PaginaInicial />;
  return (
    <EstruturaAcesso titulo="Página não encontrada" descricao="Escolha um caminho para continuar.">
      <LinkInterno href="/" className="underline">
        Voltar ao início
      </LinkInterno>
    </EstruturaAcesso>
  );
}
