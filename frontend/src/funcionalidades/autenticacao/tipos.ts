export type Usuario = {
  id: string;
  nome: string;
  email: string;
  email_verificado: true;
};

export type SessaoAutenticada = { usuario: Usuario; csrf: string };
export type Credenciais = { email: string; senha: string };
export type DadosCadastro = Credenciais & { nome: string };

export type EstadoAutenticacao = {
  situacao: 'carregando' | 'autenticado' | 'nao_autenticado' | 'indisponivel';
  usuario: Usuario | null;
  mensagem?: string;
};
