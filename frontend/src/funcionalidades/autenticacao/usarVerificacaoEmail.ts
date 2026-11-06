import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ErroHTTP, type ErrosCampos } from '../../servicos/http';
import { contextoVerificacao, intervaloReenvio, servicoVerificacao } from './verificacao';

function useVerificacaoEmail() {
  const [email, definirEmail] = useState(contextoVerificacao.email);
  const [codigo, definirCodigo] = useState('');
  const [erros, definirErros] = useState<ErrosCampos>({});
  const [mensagem, definirMensagem] = useState('');
  const [aviso, definirAviso] = useState('');
  const [sucesso, definirSucesso] = useState(false);
  const [operacao, definirOperacao] = useState<'confirmar' | 'reenviar' | null>(null);
  const [reenviarEm, definirReenviarEm] = useState(contextoVerificacao.reenviarEm);
  const [agora, definirAgora] = useState(Date.now);
  const bloqueado = useRef(false);
  const feedback = useRef<HTMLDivElement>(null);
  const formulario = useRef<HTMLFormElement>(null);
  const restantes = Math.max(0, Math.ceil((reenviarEm - agora) / 1000));

  useEffect(() => {
    if (reenviarEm <= Date.now()) return;
    const temporizador = window.setInterval(() => definirAgora(Date.now()), 1000);
    return () => window.clearInterval(temporizador);
  }, [reenviarEm]);
  useEffect(() => {
    if (mensagem || aviso || sucesso) feedback.current?.focus();
  }, [mensagem, aviso, sucesso]);

  function aguardar(segundos: number) {
    const prazo = Date.now() + segundos * 1000;
    contextoVerificacao.reenviarEm = prazo;
    definirAgora(Date.now());
    definirReenviarEm(prazo);
  }

  async function executar(acao: 'confirmar' | 'reenviar') {
    if (bloqueado.current || sucesso || (acao === 'reenviar' && Date.now() < reenviarEm)) return;
    const endereco = email.trim().toLowerCase();
    const falhas: ErrosCampos = {};
    if (endereco.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/u.test(endereco)) {
      falhas.email = 'Informe um e-mail válido com até 254 caracteres.';
    }
    if (acao === 'confirmar' && !/^[0-9]{6}$/.test(codigo)) {
      falhas.codigo = 'Informe os seis dígitos do código.';
    }
    definirErros(falhas);
    definirMensagem('');
    definirAviso('');
    const primeiro = Object.keys(falhas)[0];
    if (primeiro) {
      (formulario.current?.elements.namedItem(primeiro) as HTMLInputElement | null)?.focus();
      return;
    }
    bloqueado.current = true;
    definirOperacao(acao);
    try {
      if (acao === 'confirmar') {
        await servicoVerificacao.confirmar(endereco, codigo);
        definirCodigo('');
        contextoVerificacao.email = '';
        contextoVerificacao.reenviarEm = 0;
        definirEmail('');
        definirSucesso(true);
      } else {
        await servicoVerificacao.reenviar(endereco);
        definirCodigo('');
        aguardar(intervaloReenvio);
        definirAviso(
          'Solicitação recebida. Se o endereço for elegível, receberá instruções de verificação. A entrega pode levar alguns instantes.',
        );
      }
    } catch (erro) {
      if (erro instanceof ErroHTTP) {
        definirErros(erro.campos);
        if (erro.status === 429) aguardar(erro.aguardarSegundos ?? intervaloReenvio);
        if (erro.status === 400) definirCodigo('');
      }
      definirMensagem(
        erro instanceof Error ? erro.message : 'Não foi possível concluir a solicitação.',
      );
    } finally {
      bloqueado.current = false;
      definirOperacao(null);
    }
  }

  function enviar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    void executar('confirmar');
  }

  return {
    email,
    definirEmail,
    codigo,
    definirCodigo,
    erros,
    mensagem,
    aviso,
    sucesso,
    operacao,
    restantes,
    feedback,
    formulario,
    enviar,
    reenviar: () => void executar('reenviar'),
  };
}

export const usarVerificacaoEmail = useVerificacaoEmail;
