const dados = [
  { dia: 'Seg', cliques: 36 }, { dia: 'Ter', cliques: 58 },
  { dia: 'Qua', cliques: 43 }, { dia: 'Qui', cliques: 74 },
  { dia: 'Sex', cliques: 65 }, { dia: 'Sáb', cliques: 91 },
  { dia: 'Dom', cliques: 70 },
];

export function GraficoCliques() {
  return (
    <section aria-label="Gráfico ilustrativo de cliques" className="rounded-2xl border border-current/10 p-5 sm:p-7">
      <h3 className="text-lg font-semibold">Cliques por dia</h3>
      <p className="mt-1 text-sm opacity-70">Dados fictícios — visualização da futura área de métricas</p>
      <div className="mt-7 grid h-48 grid-cols-7 items-end gap-2 sm:gap-4" role="img" aria-label={dados.map(({dia, cliques}) => `${dia}: ${cliques} cliques`).join('; ')}>
        {dados.map(({ dia, cliques }) => (
          <div key={dia} className="flex h-full flex-col items-center justify-end gap-2">
            <div className="w-full max-w-12 rounded-t-lg bg-emerald-500" style={{ height: `${cliques}%` }} />
            <span className="text-xs font-medium opacity-70">{dia}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
