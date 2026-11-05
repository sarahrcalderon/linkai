import { ArrowRight, ChartNoAxesCombined, Link2, Moon, ShieldCheck, Sun } from 'lucide-react';
import { usarTema } from '../funcionalidades/tema/usarTema';

const recursos = [
  { titulo: 'Links personalizados', descricao: 'Crie atalhos para conversas no WhatsApp.', Icone: Link2 },
  { titulo: 'Métricas claras', descricao: 'Acompanhe cliques por dia, semana e mês.', Icone: ChartNoAxesCombined },
  { titulo: 'Acesso protegido', descricao: 'Contas verificadas e dados separados por usuário.', Icone: ShieldCheck },
];

export function PaginaInicial() {
  const { tema, alternarTema } = usarTema();
  const escuro = tema === 'escuro';

  return (
    <main className={escuro ? 'min-h-screen bg-slate-950 text-slate-100' : 'min-h-screen bg-slate-50 text-slate-900'}>
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <header className="flex min-h-20 items-center justify-between gap-4 border-b border-current/10">
          <div className="flex items-center gap-3 text-lg font-bold"><Link2 aria-hidden="true" className="text-emerald-500" /> Linkai</div>
          <button type="button" onClick={alternarTema} aria-label={escuro ? 'Ativar tema claro' : 'Ativar tema escuro'} className="rounded-xl border border-current/20 p-3 transition hover:bg-slate-500/10 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500">
            {escuro ? <Sun size={20} aria-hidden="true" /> : <Moon size={20} aria-hidden="true" />}
          </button>
        </header>
        <section className="py-20 sm:py-28">
          <span className="rounded-full border border-emerald-500/30 px-4 py-2 text-sm font-medium text-emerald-600 dark:text-emerald-400">Plataforma em desenvolvimento</span>
          <h1 className="mt-8 max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-6xl">Conecte pessoas ao seu WhatsApp com links inteligentes.</h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed opacity-75">Uma maneira simples de organizar seus links e entender o interesse do seu público com métricas fáceis de acompanhar.</p>
          <div className="mt-9 inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 font-semibold text-white">Em breve <ArrowRight size={18} aria-hidden="true" /></div>
        </section>
        <section aria-label="Recursos planejados" className="grid gap-4 pb-24 md:grid-cols-3">
          {recursos.map(({ titulo, descricao, Icone }) => (
            <article key={titulo} className="rounded-2xl border border-current/10 p-6">
              <Icone className="mb-5 text-emerald-500" size={28} aria-hidden="true" />
              <h2 className="text-xl font-semibold">{titulo}</h2>
              <p className="mt-2 leading-relaxed opacity-70">{descricao}</p>
            </article>
          ))}
        </section>
      </div>
    </main>
  );
}
