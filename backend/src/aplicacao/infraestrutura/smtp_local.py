"""SMTP de captura local: sem autenticação, TLS, relay ou destinos externos."""

import asyncio
import smtplib
from email.message import EmailMessage

from email_validator import EmailNotValidError, validate_email

from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado
from aplicacao.casos_de_uso.erros_envio_email import (
    ConfiguracaoEnvioInvalida,
    EnvioEmailIndeterminado,
    EnvioEmailPermanente,
    EnvioEmailTemporario,
)
from aplicacao.configuracao import Configuracao
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura.brevo.template import montar_template


def endereco_local(valor: str) -> str:
    try:
        email = validate_email(valor, check_deliverability=False, test_environment=True).normalized
        # Lista fechada de domínios fictícios; não é um transporte para contas reais.
        if not email.lower().endswith((".test", "@example.com", "@example.org", "@example.net")):
            raise ValueError()
        return email
    except (EmailNotValidError, ValueError, TypeError):
        raise EnvioEmailPermanente() from None


class EnvioEmailSMTPLocal:
    def __init__(self, configuracao: Configuracao) -> None:
        if (
            configuracao.ambiente != "desenvolvimento"
            or configuracao.email_provedor != "mailpit"
            or configuracao.smtp_host not in {"localhost", "127.0.0.1", "::1"}
            or configuracao.smtp_porta != 1025
        ):
            raise ConfiguracaoEnvioInvalida()
        self.configuracao = configuracao
        self.remetente = endereco_local(configuracao.smtp_remetente)

    async def enviar_verificacao(self, destinatario: str, desafio: DesafioGerado) -> None:
        destinatario = endereco_local(destinatario)
        if desafio.expira_em <= agora_utc():
            raise EnvioEmailPermanente()
        template = montar_template(desafio, "Linkai local")
        mensagem = EmailMessage()
        mensagem["From"] = self.remetente
        mensagem["To"] = destinatario
        mensagem["Subject"] = template.assunto
        mensagem["Message-ID"] = f"<{desafio.id}@linkai.test>"
        mensagem.set_content(template.texto.get_secret_value())
        mensagem.add_alternative(template.html.get_secret_value(), subtype="html")
        # O socket possui timeout; não cancelar a thread após DATA e presumir falha segura.
        await asyncio.to_thread(self._enviar, mensagem)

    def _enviar(self, mensagem: EmailMessage) -> None:
        # localhost é fixado ao loopback, sem resolver hosts arbitrários.
        host = "::1" if self.configuracao.smtp_host == "::1" else "127.0.0.1"
        try:
            cliente = smtplib.SMTP(
                host,
                1025,
                local_hostname="linkai.test",
                timeout=self.configuracao.smtp_timeout_segundos,
            )
        except (OSError, smtplib.SMTPException):
            raise EnvioEmailTemporario() from None
        try:
            cliente.send_message(mensagem)
        except smtplib.SMTPResponseException as erro:
            if 400 <= erro.smtp_code < 500:
                raise EnvioEmailTemporario() from None
            raise EnvioEmailPermanente() from None
        except smtplib.SMTPRecipientsRefused:
            raise EnvioEmailPermanente() from None
        except (OSError, smtplib.SMTPException):
            # A conexão pode cair depois de DATA; não duplicar por retentativa automática.
            raise EnvioEmailIndeterminado() from None
        finally:
            # Fechar sem QUIT evita tratar falha após aceitação como nova falha de envio.
            cliente.close()
