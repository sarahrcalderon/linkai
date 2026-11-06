import {
  ArrowRight,
  ChartNoAxesCombined,
  Link2,
  MousePointerClick,
  ShieldCheck,
} from 'lucide-react';
import { LinkInterno } from '../componentes/LinkInterno';
import { Cabecalho } from '../componentes/Cabecalho';
import { CartaoIndicador } from '../componentes/CartaoIndicador';
import { GraficoCliques } from '../componentes/GraficoCliques';

const recursos = [
  {
    titulo: 'Links personalizados',
    descricao: 'Crie atalhos para conversas no WhatsApp.',
    Icone: Link2,
  },
  {
    titulo: 'Métricas claras',
    descricao: 'Acompanhe cliques por dia, semana e mês.',
    Icone: ChartNoAxesCombined,
  },
  {
    titulo: 'Acesso protegido',
    descricao: 'Contas verificadas e dados separados por usuário.',
    Icone: ShieldCheck,
  },
];

export function PaginaInicial() {
  return (
    <main
      id="inicio"
      className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100"
    >
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <Cabecalho />
        <section className="py-16 sm:py-24">
          <span className="rounded-full border border-emerald-500/30 px-4 py-2 text-sm font-medium text-emerald-600 dark:text-emerald-400">
            Plataforma em desenvolvimento
          </span>
          <h1 className="mt-8 max-w-3xl text-4xl font-bold leading-tight tracking-tight sm:text-6xl">
            Conecte pessoas ao seu WhatsApp com links inteligentes.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-relaxed opacity-75">
            Organize seus links e entenda o interesse do público com métricas fáceis de acompanhar.
          </p>
          <nav aria-label="Acesso à conta" className="mt-9 flex flex-wrap gap-4">
            <LinkInterno
              href="/cadastro"
              className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-emerald-700 px-5 py-3 font-semibold text-white hover:bg-emerald-800"
            >
              Criar conta <ArrowRight size={18} aria-hidden="true" />
            </LinkInterno>
            <LinkInterno
              href="/login"
              className="inline-flex min-h-11 items-center rounded-xl border border-current/20 px-5 py-3 font-semibold"
            >
              Entrar
            </LinkInterno>
          </nav>
        </section>
        <section aria-label="Recursos planejados" className="grid gap-4 pb-16 md:grid-cols-3">
          {recursos.map(({ titulo, descricao, Icone }) => (
            <article key={titulo} className="rounded-2xl border border-current/10 p-6">
              <Icone className="mb-5 text-emerald-500" size={28} aria-hidden="true" />
              <h2 className="text-xl font-semibold">{titulo}</h2>
              <p className="mt-2 leading-relaxed opacity-70">{descricao}</p>
            </article>
          ))}
        </section>
        <section aria-labelledby="titulo-painel" className="pb-20">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 id="titulo-painel" className="text-2xl font-bold sm:text-3xl">
                Prévia do dashboard
              </h2>
              <p className="mt-2 opacity-70">Exemplo visual; ainda não há dados reais.</p>
            </div>
            <span className="rounded-lg border border-current/15 px-3 py-2 text-sm">
              Últimos 7 dias · demonstração
            </span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <CartaoIndicador
              titulo="Cliques totais"
              valor="437"
              Icone={MousePointerClick}
              descricao="Dados de demonstração"
            />
            <CartaoIndicador
              titulo="Links ativos"
              valor="12"
              Icone={Link2}
              descricao="Dados de demonstração"
            />
            <CartaoIndicador
              titulo="Média diária"
              valor="62"
              Icone={ChartNoAxesCombined}
              descricao="Dados de demonstração"
            />
          </div>
          <div className="mt-4">
            <GraficoCliques />
          </div>
        </section>
      </div>
    </main>
  );
}
