import { Link2, Moon, Sun } from 'lucide-react';
import { usarTema } from '../funcionalidades/tema/usarTema';
import { LinkInterno } from './LinkInterno';

export function Cabecalho() {
  const { tema, alternarTema } = usarTema();
  const escuro = tema === 'escuro';
  return (
    <header className="flex min-h-20 items-center justify-between gap-4 border-b border-current/10">
      <LinkInterno
        href="/"
        className="flex items-center gap-3 text-xl font-bold"
        aria-label="Linkai, início"
      >
        <Link2 className="text-emerald-500" aria-hidden="true" /> Linkai
      </LinkInterno>
      <button
        type="button"
        onClick={alternarTema}
        aria-label={escuro ? 'Ativar tema claro' : 'Ativar tema escuro'}
        className="rounded-xl border border-current/20 p-3 transition hover:bg-current/5 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500"
      >
        {escuro ? <Sun size={20} aria-hidden="true" /> : <Moon size={20} aria-hidden="true" />}
      </button>
    </header>
  );
}
