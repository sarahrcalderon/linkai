import { useState } from 'react';
import { Activity, Link2, Pause } from 'lucide-react';
import { Botao } from '../../componentes/Botao';
import { CartaoIndicador } from '../../componentes/CartaoIndicador';
import { Feedback } from '../../componentes/Feedback';
import { urlPublica, type LinkPersonalizado } from '../links/servico';
import { GraficoAcessos } from './GraficoAcessos';
import { usarEstatisticas } from './usarEstatisticas';
import type { Estatisticas, Periodo, Resumo } from './servico';

function resumo(dados: Estatisticas): dados is Resumo {
  return 'links_ativos' in dados && 'links_inativos' in dados;
}

export function Analytics({
  link,
  voltar,
}: {
  link: LinkPersonalizado | null;
  voltar: () => void;
}) {
  const [dias, definirDias] = useState<Periodo>(7);
  const { dados, erro, carregando, recarregar } = usarEstatisticas(dias, link?.id);
  return (
    <section
      id="analytics"
      aria-labelledby="titulo-analytics"
      className="mt-10 min-w-0 scroll-mt-6 rounded-2xl border border-current/10 p-4 sm:p-7"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h2
            id="titulo-analytics"
            tabIndex={-1}
            className="text-2xl font-bold break-words focus-visible:outline-2 focus-visible:outline-emerald-500"
          >
            {link ? `Estatísticas de ${link.nome}` : 'Visão geral de Analytics'}
          </h2>
          {link && (
            <>
              <p className="mt-3 text-sm break-all">{urlPublica(link.slug)}</p>
              <Botao className="mt-3" variante="secundaria" onClick={voltar}>
                Voltar à visão geral
              </Botao>
            </>
          )}
        </div>
        <div className="w-full sm:w-auto">
          <label htmlFor="periodo-analytics" className="mb-2 block text-sm font-semibold">
            Período
          </label>
          <select
            id="periodo-analytics"
            value={dias}
            onChange={(evento) => definirDias(Number(evento.target.value) as Periodo)}
            className="min-h-11 w-full rounded-xl border border-current/25 bg-slate-50 px-3 py-2 text-base focus-visible:outline-2 focus-visible:outline-emerald-500 dark:bg-slate-950"
          >
            {[7, 30, 90].map((valor) => (
              <option key={valor} value={valor}>
                Últimos {valor} dias
              </option>
            ))}
          </select>
        </div>
      </div>
      <p className="mt-5 text-sm leading-relaxed">
        Estas métricas representam acessos registrados, não visitantes únicos, conversas iniciadas
        ou mensagens enviadas.
      </p>
      <div className="mt-5" aria-busy={carregando}>
        {carregando && (
          <p role="status" className="rounded-xl bg-current/5 p-5">
            Carregando estatísticas…
          </p>
        )}
        {erro && (
          <>
            <Feedback mensagem={erro} />
            <Botao className="mt-3" variante="secundaria" onClick={recarregar}>
              Tentar novamente
            </Botao>
          </>
        )}
        {dados && (
          <>
            <p className="mb-4 text-sm">
              Últimos {dias} dias · UTC · Até{' '}
              {new Intl.DateTimeFormat('pt-BR', {
                dateStyle: 'short',
                timeStyle: 'short',
                timeZone: 'UTC',
              }).format(new Date(dados.data_final))}{' '}
              UTC
            </p>
            <div className="grid gap-4 sm:grid-cols-3">
              <CartaoIndicador
                titulo="Acessos registrados no período"
                valor={dados.total_acessos.toLocaleString('pt-BR')}
                Icone={Activity}
                descricao="Total informado pela API"
              />
              {resumo(dados) && (
                <>
                  <CartaoIndicador
                    titulo="Links ativos"
                    valor={dados.links_ativos.toLocaleString('pt-BR')}
                    Icone={Link2}
                    descricao="Estado atual dos seus links"
                  />
                  <CartaoIndicador
                    titulo="Links inativos"
                    valor={dados.links_inativos.toLocaleString('pt-BR')}
                    Icone={Pause}
                    descricao="Estado atual dos seus links"
                  />
                </>
              )}
            </div>
            {dados.total_acessos === 0 && (
              <p role="status" className="mt-5 rounded-xl border border-current/15 p-4">
                Nenhum acesso registrado neste período.
              </p>
            )}
            {resumo(dados) && dados.links_ativos + dados.links_inativos === 0 && (
              <p className="mt-3">
                Você ainda não tem links. Crie seu primeiro link em Meus links.
              </p>
            )}
            <GraficoAcessos key={`${link?.id || 'resumo'}:${dias}`} serie={dados.serie_diaria} />
          </>
        )}
      </div>
    </section>
  );
}
