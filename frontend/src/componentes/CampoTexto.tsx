import type { InputHTMLAttributes } from 'react';

type Propriedades = InputHTMLAttributes<HTMLInputElement> & {
  rotulo: string;
  identificador: string;
  erro?: string;
};

export function CampoTexto({ rotulo, identificador, erro, ...propriedades }: Propriedades) {
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={identificador} className="text-sm font-semibold">{rotulo}</label>
      <input
        id={identificador}
        aria-invalid={Boolean(erro)}
        aria-describedby={erro ? `${identificador}-erro` : undefined}
        className="min-h-11 rounded-xl border border-current/20 bg-transparent px-4 py-3 text-base outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
        {...propriedades}
      />
      {erro && <p id={`${identificador}-erro`} role="alert" className="text-sm text-red-600 dark:text-red-400">{erro}</p>}
    </div>
  );
}
