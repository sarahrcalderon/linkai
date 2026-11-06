import type { ButtonHTMLAttributes, ReactNode } from 'react';

type Propriedades = ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: 'principal' | 'secundaria';
  children: ReactNode;
};

export function Botao({
  variante = 'principal',
  className = '',
  children,
  ...propriedades
}: Propriedades) {
  const estilo =
    variante === 'principal'
      ? 'bg-emerald-700 text-white hover:bg-emerald-800'
      : 'border border-current/20 hover:bg-current/5';

  return (
    <button
      {...propriedades}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-xl px-5 py-3 text-base font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500 disabled:cursor-not-allowed disabled:opacity-50 ${estilo} ${className}`}
    >
      {children}
    </button>
  );
}
