import { useEffect, useState } from 'react';

type Tema = 'claro' | 'escuro';

function obterTemaInicial(): Tema {
  const salvo = localStorage.getItem('tema');
  if (salvo === 'claro' || salvo === 'escuro') return salvo;
  return typeof window.matchMedia === 'function' && window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'escuro'
    : 'claro';
}

export function usarTema() {
  const [tema, definirTema] = useState<Tema>(obterTemaInicial);

  useEffect(() => {
    document.documentElement.dataset.tema = tema;
    localStorage.setItem('tema', tema);
  }, [tema]);

  return { tema, alternarTema: () => definirTema(tema === 'claro' ? 'escuro' : 'claro') };
}
