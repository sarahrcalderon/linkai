import { LoaderCircle } from 'lucide-react';
import { usarFormularioAutenticacao } from '../funcionalidades/autenticacao/usarFormularioAutenticacao';
import { Botao } from './Botao';
import { CampoTexto } from './CampoTexto';
import { Feedback } from './Feedback';
import { LinkInterno } from './LinkInterno';

export function FormularioAutenticacao({ cadastro }: { cadastro: boolean }) {
  const { enviar, enviando, erros, mensagem, sucesso, feedback } =
    usarFormularioAutenticacao(cadastro);
  return (
    <>
      <form
        onSubmit={enviar}
        noValidate
        aria-label={cadastro ? 'Cadastro' : 'Login'}
        aria-busy={enviando}
        className="flex min-w-0 flex-col gap-5"
      >
        {cadastro && (
          <CampoTexto
            name="nome"
            rotulo="Nome"
            identificador="nome"
            autoComplete="name"
            required
            minLength={2}
            maxLength={100}
            disabled={enviando}
            erro={erros.nome}
          />
        )}
        <CampoTexto
          name="email"
          rotulo="E-mail"
          identificador="email"
          type="email"
          autoComplete="email"
          required
          maxLength={254}
          disabled={enviando}
          erro={erros.email}
        />
        <CampoTexto
          name="senha"
          rotulo="Senha"
          identificador="senha"
          type="password"
          autoComplete={cadastro ? 'new-password' : 'current-password'}
          required
          disabled={enviando}
          erro={erros.senha}
        />
        {cadastro && (
          <p className="text-sm leading-relaxed opacity-75">
            Use de 12 a 128 caracteres. Sua conta precisará de verificação de e-mail para acessar a
            área privada.
          </p>
        )}
        <Feedback referencia={feedback} mensagem={mensagem || sucesso} sucesso={Boolean(sucesso)} />
        <Botao type="submit" disabled={enviando} className="w-full">
          {enviando && <LoaderCircle size={18} className="animate-spin" aria-hidden="true" />}
          {enviando ? 'Enviando…' : cadastro ? 'Criar conta' : 'Entrar'}
        </Botao>
      </form>
      <p className="mt-6 text-center leading-relaxed">
        {cadastro ? 'Já tem uma conta? ' : 'Ainda não tem conta? '}
        <LinkInterno
          href={cadastro ? '/login' : '/cadastro'}
          className="font-semibold text-emerald-700 underline underline-offset-4 dark:text-emerald-400"
        >
          {cadastro ? 'Entrar' : 'Criar conta'}
        </LinkInterno>
      </p>
    </>
  );
}
