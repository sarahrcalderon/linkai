import type { ErrosCampos } from '../../servicos/http';
import type { DadosCadastro } from './tipos';

export function validarFormulario(dados: DadosCadastro, cadastro: boolean): ErrosCampos {
  const erros: ErrosCampos = {};
  const tamanhoNome = Array.from(dados.nome.trim()).length;
  if (
    cadastro &&
    (tamanhoNome < 2 || tamanhoNome > 100 || /[\p{C}\p{Zl}\p{Zp}]/u.test(dados.nome.trim()))
  ) {
    erros.nome = 'Informe um nome com 2 a 100 caracteres, sem caracteres de controle.';
  }
  if (dados.email.trim().length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(dados.email.trim())) {
    erros.email = 'Informe um e-mail válido com até 254 caracteres.';
  }
  const tamanhoSenha = Array.from(dados.senha).length;
  if (
    tamanhoSenha < (cadastro ? 12 : 1) ||
    tamanhoSenha > 128 ||
    (cadastro && (!dados.senha.trim() || /[\p{C}\p{Zl}\p{Zp}]/u.test(dados.senha)))
  ) {
    erros.senha = cadastro
      ? 'Informe uma senha com 12 a 128 caracteres.'
      : 'Informe uma senha com 1 a 128 caracteres.';
  }
  return erros;
}
