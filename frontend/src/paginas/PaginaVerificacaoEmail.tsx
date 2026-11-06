import { Botao } from '../componentes/Botao';
import { CampoTexto } from '../componentes/CampoTexto';
import { EstruturaAcesso } from '../componentes/EstruturaAcesso';
import { Feedback } from '../componentes/Feedback';
import { LinkInterno } from '../componentes/LinkInterno';
import { usarVerificacaoEmail } from '../funcionalidades/autenticacao/usarVerificacaoEmail';

export function PaginaVerificacaoEmail() {
  const fluxo = usarVerificacaoEmail();
  const ocupado = fluxo.operacao !== null;
  return (
    <EstruturaAcesso
      titulo="Verifique seu e-mail"
      descricao="Se o endereço for elegível, receberá instruções de verificação. Confira também a pasta de spam."
    >
      {fluxo.sucesso ? (
        <Feedback
          referencia={fluxo.feedback}
          sucesso
          mensagem="E-mail verificado. Entre na sua conta para continuar."
        />
      ) : (
        <form
          ref={fluxo.formulario}
          onSubmit={fluxo.enviar}
          noValidate
          aria-label="Verificação de e-mail"
          aria-busy={ocupado}
          className="flex min-w-0 flex-col gap-5"
        >
          <p className="text-sm leading-relaxed">
            Informe seu e-mail e o código mais recente. Se atualizou esta página, preencha o
            endereço novamente.
          </p>
          <CampoTexto
            identificador="email"
            name="email"
            rotulo="E-mail"
            type="email"
            autoComplete="email"
            required
            maxLength={254}
            value={fluxo.email}
            onChange={(evento) => {
              fluxo.definirEmail(evento.target.value);
              fluxo.definirCodigo('');
            }}
            disabled={ocupado}
            erro={fluxo.erros.email}
          />
          <CampoTexto
            identificador="codigo"
            name="codigo"
            rotulo="Código de seis dígitos"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            required
            maxLength={6}
            value={fluxo.codigo}
            onChange={(evento) => fluxo.definirCodigo(evento.target.value)}
            disabled={ocupado}
            erro={fluxo.erros.codigo}
          />
          <Feedback
            referencia={fluxo.feedback}
            mensagem={fluxo.mensagem || fluxo.aviso}
            sucesso={Boolean(fluxo.aviso)}
          />
          <Botao type="submit" disabled={ocupado}>
            {fluxo.operacao === 'confirmar' ? 'Confirmando…' : 'Confirmar e-mail'}
          </Botao>
          <Botao
            type="button"
            variante="secundaria"
            onClick={fluxo.reenviar}
            disabled={ocupado || fluxo.restantes > 0}
            aria-describedby="espera-reenvio"
          >
            {fluxo.operacao === 'reenviar' ? 'Solicitando…' : 'Reenviar código'}
          </Botao>
          <p id="espera-reenvio" className="text-sm leading-relaxed" role="timer" aria-live="off">
            {fluxo.restantes > 0
              ? `Aguarde ${fluxo.restantes} segundos para solicitar outro código.`
              : 'Você pode solicitar outro código. Os limites de envio continuam sendo aplicados pelo serviço.'}
          </p>
          <span className="sr-only" role="status">
            {fluxo.restantes === 0 ? 'Reenvio disponível.' : ''}
          </span>
        </form>
      )}
      <p className="mt-6 text-center">
        <LinkInterno
          href="/login"
          className="font-semibold text-emerald-700 underline underline-offset-4 dark:text-emerald-400"
        >
          Ir para o login
        </LinkInterno>
      </p>
    </EstruturaAcesso>
  );
}
