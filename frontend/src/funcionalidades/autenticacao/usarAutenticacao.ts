import { useContext, useSyncExternalStore } from 'react';
import { ContextoAutenticacao } from './contexto';

function useAutenticacao() {
  const gerenciador = useContext(ContextoAutenticacao);
  if (!gerenciador) throw new Error('Provedor de autenticação não configurado.');
  const estado = useSyncExternalStore(gerenciador.inscrever, gerenciador.obterEstado);
  return {
    ...estado,
    entrar: gerenciador.entrar,
    sair: gerenciador.sair,
    revalidar: gerenciador.revalidar,
  };
}

export const usarAutenticacao = useAutenticacao;
