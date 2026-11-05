import { useEffect, useState, type ReactNode } from 'react';
import { ContextoAutenticacao } from './contexto';
import { GerenciadorAutenticacao } from './gerenciador';

export function ProvedorAutenticacao({ children }: { children: ReactNode }) {
  const [gerenciador] = useState(() => new GerenciadorAutenticacao());
  useEffect(() => {
    void gerenciador.iniciar();
    const aoRetornar = () => {
      if (document.visibilityState === 'visible') void gerenciador.revalidar();
    };
    window.addEventListener('focus', aoRetornar);
    document.addEventListener('visibilitychange', aoRetornar);
    return () => {
      window.removeEventListener('focus', aoRetornar);
      document.removeEventListener('visibilitychange', aoRetornar);
    };
  }, [gerenciador]);
  return (
    <ContextoAutenticacao.Provider value={gerenciador}>{children}</ContextoAutenticacao.Provider>
  );
}
