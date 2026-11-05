import { useSyncExternalStore } from 'react';

function inscrever(ouvinte: () => void) {
  window.addEventListener('popstate', ouvinte);
  return () => window.removeEventListener('popstate', ouvinte);
}

export function navegar(caminho: string, substituir = false) {
  if (window.location.pathname === caminho) return;
  window.history[substituir ? 'replaceState' : 'pushState'](null, '', caminho);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

function useNavegacao() {
  return useSyncExternalStore(inscrever, () => window.location.pathname);
}

export const usarNavegacao = useNavegacao;
