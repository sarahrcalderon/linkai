import { useRef, useState } from 'react';
import { LogOut, RefreshCw } from 'lucide-react';
import { Botao } from '../componentes/Botao';
import { Cabecalho } from '../componentes/Cabecalho';
import { Feedback } from '../componentes/Feedback';
import { usarAutenticacao } from '../funcionalidades/autenticacao/usarAutenticacao';
import { navegar } from '../navegacao/usarNavegacao';

export function PaginaDashboard() {
  const { usuario, sair, revalidar } = usarAutenticacao();
  const [ocupado, definirOcupado] = useState(false);
  const [erro, definirErro] = useState('');
  const bloqueado = useRef(false);
  async function executar(encerrar: boolean) {
    if (bloqueado.current) return;
    bloqueado.current = true;
    definirOcupado(true);
    definirErro('');
    try {
      if (encerrar) {
        await sair();
        navegar('/login', true);
      } else await revalidar(true);
    } catch (falha) {
      definirErro(falha instanceof Error ? falha.message : 'Não foi possível encerrar a sessão.');
    } finally {
      bloqueado.current = false;
      definirOcupado(false);
    }
  }
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <Cabecalho />
        <section className="mx-auto max-w-2xl py-12 sm:py-20" aria-labelledby="titulo-dashboard">
          <h1 id="titulo-dashboard" className="text-3xl font-bold break-words">
            Olá, {usuario?.nome}.
          </h1>
          <p className="mt-4 leading-relaxed">Sua conta está conectada ao Linkai.</p>
          <p className="mt-2 break-all opacity-75">{usuario?.email}</p>
          <div className="my-8 rounded-2xl border border-current/15 p-6">
            <h2 className="text-xl font-semibold">Seu espaço está pronto</h2>
            <p className="mt-3 leading-relaxed opacity-75">
              Os recursos de links e estatísticas estarão disponíveis em breve.
            </p>
          </div>
          <Feedback mensagem={erro} />
          <div className="mt-5 flex flex-wrap gap-3" aria-busy={ocupado}>
            <Botao variante="secundaria" disabled={ocupado} onClick={() => void executar(false)}>
              <RefreshCw size={18} aria-hidden="true" /> Atualizar sessão
            </Botao>
            <Botao disabled={ocupado} onClick={() => void executar(true)}>
              <LogOut size={18} aria-hidden="true" /> {ocupado ? 'Aguarde…' : 'Sair'}
            </Botao>
          </div>
        </section>
      </div>
    </main>
  );
}
