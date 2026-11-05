import type { ReactNode } from 'react';
import { ShieldCheck } from 'lucide-react';
import { Cabecalho } from './Cabecalho';

export function EstruturaAcesso({
  titulo,
  descricao,
  children,
}: {
  titulo: string;
  descricao: string;
  children: ReactNode;
}) {
  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <Cabecalho />
        <section
          className="mx-auto w-full min-w-0 max-w-md py-12 sm:py-20"
          aria-labelledby="titulo-acesso"
        >
          <ShieldCheck
            className="mb-5 text-emerald-600 dark:text-emerald-400"
            size={32}
            aria-hidden="true"
          />
          <h1 id="titulo-acesso" className="text-3xl font-bold tracking-tight sm:text-4xl">
            {titulo}
          </h1>
          <p className="mt-3 mb-8 leading-relaxed opacity-75">{descricao}</p>
          {children}
        </section>
      </div>
    </main>
  );
}
