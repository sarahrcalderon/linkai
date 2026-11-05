import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ErroHTTP, type ErrosCampos } from '../../servicos/http';
import { servicoAutenticacao } from './servico';
import { usarAutenticacao } from './usarAutenticacao';
import { validarFormulario } from './validacao';
import { navegar } from '../../navegacao/usarNavegacao';

function useFormularioAutenticacao(cadastro: boolean) {
  const { entrar } = usarAutenticacao();
  const bloqueado = useRef(false);
  const feedback = useRef<HTMLDivElement>(null);
  const [enviando, definirEnviando] = useState(false);
  const [erros, definirErros] = useState<ErrosCampos>({});
  const [mensagem, definirMensagem] = useState('');
  const [sucesso, definirSucesso] = useState('');
  useEffect(() => {
    if (mensagem || sucesso) feedback.current?.focus();
  }, [mensagem, sucesso]);

  async function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    if (bloqueado.current) return;
    const formulario = evento.currentTarget;
    const campos = new FormData(formulario);
    const dados = {
      nome: String(campos.get('nome') || '').trim(),
      email: String(campos.get('email') || '')
        .trim()
        .toLowerCase(),
      senha: String(campos.get('senha') || ''),
    };
    const errosAtuais = validarFormulario(dados, cadastro);
    definirErros(errosAtuais);
    definirMensagem('');
    definirSucesso('');
    const primeiroCampo = Object.keys(errosAtuais)[0];
    if (primeiroCampo) {
      (formulario.elements.namedItem(primeiroCampo) as HTMLInputElement | null)?.focus();
      return;
    }
    bloqueado.current = true;
    definirEnviando(true);
    try {
      if (cadastro) {
        definirSucesso(await servicoAutenticacao.cadastrar(dados));
        formulario.reset();
      } else {
        await entrar({ email: dados.email, senha: dados.senha });
        formulario.reset();
        navegar('/dashboard', true);
      }
    } catch (erro) {
      if (erro instanceof ErroHTTP) definirErros(erro.campos);
      definirMensagem(
        erro instanceof Error ? erro.message : 'Não foi possível concluir a solicitação.',
      );
    } finally {
      const senha = formulario.elements.namedItem('senha') as HTMLInputElement | null;
      if (senha) senha.value = '';
      bloqueado.current = false;
      definirEnviando(false);
      feedback.current?.focus();
    }
  }

  return { enviar, enviando, erros, mensagem, sucesso, feedback };
}

export const usarFormularioAutenticacao = useFormularioAutenticacao;
