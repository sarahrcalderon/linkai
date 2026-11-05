import { createContext } from 'react';
import type { GerenciadorAutenticacao } from './gerenciador';

export const ContextoAutenticacao = createContext<GerenciadorAutenticacao | null>(null);
