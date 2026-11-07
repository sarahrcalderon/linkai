import { useState } from 'react';
import { formatarDia, type DiaAcessos } from './servico';

export function GraficoAcessos({ serie }: { serie: DiaAcessos[] }) {
  const [indice, definirIndice] = useState(0);
  const selecionado = Math.min(indice, serie.length - 1);
  const dia = serie[selecionado];
  const maximo = Math.max(1, ...serie.map((item) => item.acessos));
  const x = (i: number) => 35 + (i * 630) / Math.max(1, serie.length - 1);
  const y = (valor: number) => 170 - (valor / maximo) * 145;
  return (
    <div className="mt-6 min-w-0">
      <h3 className="text-lg font-semibold">Evolução diária</h3>
      <p className="mt-2 text-sm">Datas em UTC. O dia atual está parcial.</p>
      <p className="mt-4 text-xs tabular-nums">
        Escala: 0 a {maximo.toLocaleString('pt-BR')} acessos
      </p>
      <svg
        viewBox="0 0 700 205"
        className="mt-4 w-full text-emerald-700 dark:text-emerald-300"
        role="img"
        aria-label="Evolução dos acessos registrados por dia. Valores na tabela abaixo."
      >
        <line x1="35" y1="170" x2="665" y2="170" stroke="currentColor" />
        <polyline
          points={serie.map((item, i) => `${x(i)},${y(item.acessos)}`).join(' ')}
          fill="none"
          stroke="currentColor"
          strokeWidth="3"
        />
        <circle cx={x(selecionado)} cy={y(dia.acessos)} r="5" fill="currentColor" />
      </svg>
      <div className="flex justify-between gap-2 text-xs tabular-nums" aria-hidden="true">
        {[0, Math.floor((serie.length - 1) / 2), serie.length - 1].map((i) => (
          <span key={i}>{formatarDia(serie[i].data)}</span>
        ))}
      </div>
      <label className="mt-3 block font-medium" htmlFor="dia-grafico">
        Consultar dia do gráfico
      </label>
      <input
        id="dia-grafico"
        type="range"
        min="0"
        max={serie.length - 1}
        value={selecionado}
        onChange={(evento) => definirIndice(Number(evento.target.value))}
        aria-valuetext={`${formatarDia(dia.data)}: ${dia.acessos} acessos`}
        aria-describedby="detalhe-dia"
        className="mt-2 min-h-11 accent-emerald-700 focus-visible:outline-2 focus-visible:outline-emerald-500"
      />
      <p
        id="detalhe-dia"
        role="tooltip"
        aria-live="polite"
        className="rounded-xl bg-current/5 p-3 tabular-nums"
      >
        {formatarDia(dia.data)}: {dia.acessos.toLocaleString('pt-BR')} acessos registrados
      </p>
      <details className="mt-4">
        <summary className="min-h-11 cursor-pointer rounded-lg py-3 font-semibold focus-visible:outline-2 focus-visible:outline-emerald-500">
          Ver tabela diária
        </summary>
        <div className="mt-2 max-h-80 overflow-y-auto rounded-xl border border-current/15">
          <table className="w-full text-left text-sm tabular-nums">
            <caption className="p-3 text-left">Acessos registrados por dia (UTC)</caption>
            <thead>
              <tr>
                <th scope="col" className="p-3">
                  Data (UTC)
                </th>
                <th scope="col" className="p-3 text-right">
                  Acessos
                </th>
              </tr>
            </thead>
            <tbody>
              {serie.map((item) => (
                <tr key={item.data} className="border-t border-current/10">
                  <th scope="row" className="p-3 font-normal">
                    {formatarDia(item.data)}/{item.data.slice(0, 4)}
                  </th>
                  <td className="p-3 text-right">{item.acessos.toLocaleString('pt-BR')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
