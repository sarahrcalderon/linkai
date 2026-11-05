import type { Ref } from 'react';

export function Feedback({
  mensagem,
  sucesso = false,
  referencia,
}: {
  mensagem: string;
  sucesso?: boolean;
  referencia?: Ref<HTMLDivElement>;
}) {
  if (!mensagem) return null;
  return (
    <div
      ref={referencia}
      tabIndex={-1}
      role={sucesso ? 'status' : 'alert'}
      className={`rounded-xl border p-4 text-base leading-relaxed break-words focus-visible:outline-2 focus-visible:outline-emerald-500 ${sucesso ? 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300' : 'border-red-500/40 text-red-700 dark:text-red-300'}`}
    >
      {mensagem}
    </div>
  );
}
