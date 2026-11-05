import type { LucideIcon } from 'lucide-react';

type Propriedades = { titulo: string; valor: string; Icone: LucideIcon; descricao: string };

export function CartaoIndicador({ titulo, valor, Icone, descricao }: Propriedades) {
  return (
    <article className="rounded-2xl border border-current/10 bg-current/[0.025] p-5">
      <div className="flex items-center justify-between gap-2 text-sm opacity-75">
        <h3>{titulo}</h3>
        <Icone size={20} aria-hidden="true" />
      </div>
      <p className="mt-3 text-3xl font-bold tabular-nums">{valor}</p>
      <p className="mt-2 text-sm opacity-70">{descricao}</p>
    </article>
  );
}
