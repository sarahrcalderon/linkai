import { useEffect, useRef, type ReactNode } from 'react';

export function Dialogo({
  titulo,
  fechar,
  children,
  focoRetorno,
}: {
  titulo: string;
  fechar: () => void;
  children: ReactNode;
  focoRetorno?: HTMLElement | null;
}) {
  const dialogo = useRef<HTMLDialogElement>(null);
  const fecharAtual = useRef(fechar);
  fecharAtual.current = fechar;
  useEffect(() => {
    const anterior = focoRetorno || (document.activeElement as HTMLElement | null);
    const elemento = dialogo.current;
    elemento?.showModal();
    return () => {
      elemento?.close();
      anterior?.focus();
    };
  }, [focoRetorno]);
  return (
    <dialog
      ref={dialogo}
      aria-labelledby="titulo-dialogo"
      onKeyDown={(evento) => {
        if (evento.key !== 'Tab') return;
        const controles = Array.from(
          evento.currentTarget.querySelectorAll<HTMLElement>(
            'button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),a[href],[tabindex="0"]',
          ),
        ).filter((controle) => controle.getClientRects().length > 0);
        const primeiro = controles[0],
          ultimo = controles[controles.length - 1];
        if (evento.shiftKey && document.activeElement === primeiro) {
          evento.preventDefault();
          ultimo?.focus();
        } else if (!evento.shiftKey && document.activeElement === ultimo) {
          evento.preventDefault();
          primeiro?.focus();
        }
      }}
      onCancel={(evento) => {
        evento.preventDefault();
        fecharAtual.current();
      }}
      className="m-auto max-h-[90dvh] w-[calc(100%_-_2rem)] max-w-xl overflow-y-auto rounded-2xl border border-current/15 bg-slate-50 p-5 text-slate-900 backdrop:bg-slate-950/60 sm:p-8 dark:bg-slate-950 dark:text-slate-100"
    >
      <h2 id="titulo-dialogo" className="mb-6 text-2xl font-bold">
        {titulo}
      </h2>
      {children}
    </dialog>
  );
}
