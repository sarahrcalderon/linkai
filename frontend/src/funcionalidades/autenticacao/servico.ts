import { requisitar } from '../../servicos/http';
import type { Credenciais, DadosCadastro, SessaoAutenticada } from './tipos';

function validarSessao(dados: unknown): SessaoAutenticada {
  if (typeof dados !== 'object' || dados === null)
    throw new Error('Resposta de autenticação inválida.');
  const sessao = dados as Partial<SessaoAutenticada>;
  const usuario = sessao.usuario;
  if (
    !usuario ||
    typeof usuario.id !== 'string' ||
    typeof usuario.nome !== 'string' ||
    typeof usuario.email !== 'string' ||
    usuario.email_verificado !== true ||
    typeof sessao.csrf !== 'string' ||
    !/^[a-f0-9]{64}$/.test(sessao.csrf)
  ) {
    throw new Error('Não foi possível confirmar a autenticação. Tente novamente.');
  }
  return { usuario, csrf: sessao.csrf };
}

export const servicoAutenticacao = {
  async cadastrar(dados: DadosCadastro): Promise<string> {
    const resposta = await requisitar('/api/autenticacao/cadastro', 202, {
      method: 'POST',
      body: JSON.stringify(dados),
    });
    if (
      !resposta ||
      typeof resposta !== 'object' ||
      !('mensagem' in resposta) ||
      typeof resposta.mensagem !== 'string'
    ) {
      throw new Error('Resposta de cadastro inesperada. Tente novamente.');
    }
    return resposta.mensagem;
  },
  async entrar(dados: Credenciais): Promise<SessaoAutenticada> {
    return validarSessao(
      await requisitar('/api/autenticacao/login', 200, {
        method: 'POST',
        body: JSON.stringify(dados),
      }),
    );
  },
  async consultar(): Promise<SessaoAutenticada> {
    return validarSessao(await requisitar('/api/usuarios/me', 200));
  },
  async sair(csrf: string): Promise<void> {
    await requisitar('/api/autenticacao/logout', 204, {
      method: 'POST',
      headers: { 'X-CSRF-Token': csrf },
    });
  },
};
