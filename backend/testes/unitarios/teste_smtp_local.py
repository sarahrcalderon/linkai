import smtplib
from contextlib import asynccontextmanager
from datetime import timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr, ValidationError

from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado
from aplicacao.casos_de_uso.erros_envio_email import (
    ConfiguracaoEnvioInvalida,
    EnvioEmailIndeterminado,
    EnvioEmailPermanente,
    EnvioEmailTemporario,
)
from aplicacao.casos_de_uso.processar_emails import ProcessarEmails
from aplicacao.configuracao import Configuracao
from aplicacao.dominio.entrega_email import EntregaReservada
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura import fabrica_envio
from aplicacao.infraestrutura.brevo.configuracao import ConfiguracaoBrevo
from aplicacao.infraestrutura.cifra_outbox import CifraOutbox
from aplicacao.infraestrutura.smtp_local import EnvioEmailSMTPLocal


def configurar(**ajustes):
    return Configuracao(_env_file=None, **{"email_provedor": "mailpit", **ajustes})


def desafio():
    return DesafioGerado(
        id=uuid4(),
        usuario_id=uuid4(),
        codigo="012345",
        expira_em=agora_utc() + timedelta(minutes=10),
    )


async def test_envio_smtp_local_template_mime_e_privacidade(monkeypatch, caplog):
    caplog.set_level("DEBUG")
    cliente = MagicMock()
    construir = MagicMock(return_value=cliente)
    monkeypatch.setattr(smtplib, "SMTP", construir)
    async with fabrica_envio.criar_servico_email(configurar()) as envio:
        await envio.enviar_verificacao("teste@example.com", desafio())
    construir.assert_called_once_with("127.0.0.1", 1025, local_hostname="linkai.test", timeout=5)
    mensagem = cliente.send_message.call_args.args[0]
    assert mensagem["To"] == "teste@example.com"
    assert mensagem["From"] == "nao-responda@linkai.test"
    assert mensagem.get_body(preferencelist=("plain",)) is not None
    assert mensagem.get_body(preferencelist=("html",)) is not None
    assert "012345" in mensagem.get_body(preferencelist=("plain",)).get_content()
    cliente.login.assert_not_called()
    cliente.starttls.assert_not_called()
    cliente.set_debuglevel.assert_not_called()
    cliente.close.assert_called_once()
    assert "012345" not in caplog.text and "teste@example.com" not in caplog.text


@pytest.mark.parametrize(
    "ajuste",
    [
        {"smtp_host": "smtp.externo.example"},
        {"smtp_porta": 25},
        {"ambiente": "producao"},
        {"ambiente": "teste"},
    ],
)
def test_mailpit_restrito_a_desenvolvimento_loopback_e_porta(ajuste):
    with pytest.raises(ValidationError):
        configurar(**ajuste)


@pytest.mark.parametrize(
    "destinatario", ["pessoa@proton.me", "a@outlook.com", "a@example.com\r\nBcc:b@example.com"]
)
async def test_destino_real_ou_injecao_bloqueados_antes_de_socket(destinatario, monkeypatch):
    construir = MagicMock()
    monkeypatch.setattr(smtplib, "SMTP", construir)
    with pytest.raises(EnvioEmailPermanente):
        await EnvioEmailSMTPLocal(configurar()).enviar_verificacao(destinatario, desafio())
    construir.assert_not_called()


async def test_conexao_smtp_falha_temporaria_sem_expor_detalhes(monkeypatch, caplog):
    construir = MagicMock(side_effect=ConnectionRefusedError("detalhe privado 012345"))
    monkeypatch.setattr(smtplib, "SMTP", construir)
    with pytest.raises(EnvioEmailTemporario) as erro:
        await EnvioEmailSMTPLocal(configurar()).enviar_verificacao("teste@example.com", desafio())
    assert "012345" not in str(erro.value) + caplog.text
    assert construir.call_count == 1


@pytest.mark.parametrize(
    "falha,tipo",
    [
        (TimeoutError("privado"), EnvioEmailIndeterminado),
        (smtplib.SMTPDataError(451, b"privado"), EnvioEmailTemporario),
        (smtplib.SMTPDataError(550, b"privado"), EnvioEmailPermanente),
    ],
)
async def test_classifica_resposta_e_transporte_sem_retentar(monkeypatch, falha, tipo):
    cliente = MagicMock()
    cliente.send_message.side_effect = falha
    monkeypatch.setattr(smtplib, "SMTP", MagicMock(return_value=cliente))
    with pytest.raises(tipo):
        await EnvioEmailSMTPLocal(configurar()).enviar_verificacao("teste@example.com", desafio())
    cliente.send_message.assert_called_once()
    cliente.close.assert_called_once()


@pytest.mark.parametrize("provedor", ["desativado", "brevo"])
async def test_worker_nao_ativa_brevo_em_desenvolvimento(provedor, monkeypatch):
    construir = MagicMock()
    monkeypatch.setattr(fabrica_envio, "criar_envio_brevo", construir)
    with pytest.raises(ConfiguracaoEnvioInvalida):
        async with fabrica_envio.criar_servico_email(configurar(email_provedor=provedor)):
            pytest.fail("Provedor inseguro foi ativado.")
    construir.assert_not_called()


async def test_brevo_preservado_com_selecao_explicita_em_producao(monkeypatch):
    adaptador = object()

    @asynccontextmanager
    async def brevo(configuracao):
        assert isinstance(configuracao, ConfiguracaoBrevo)
        yield adaptador

    monkeypatch.setattr(fabrica_envio, "criar_envio_brevo", brevo)
    monkeypatch.setattr(
        fabrica_envio,
        "ConfiguracaoBrevo",
        lambda: ConfiguracaoBrevo(
            _env_file=None, api_key="chave-ficticia", email_remetente="remetente@example.com"
        ),
    )
    async with fabrica_envio.criar_servico_email(
        configurar(
            ambiente="producao",
            email_provedor="brevo",
            origens_permitidas=["https://app.example.com"],
        )
    ) as envio:
        assert envio is adaptador


async def test_outbox_existente_decifra_envia_e_conclui_sem_segunda_implementacao(monkeypatch):
    cifra = CifraOutbox(SecretStr(Fernet.generate_key().decode()))
    gerado = desafio()
    reserva = EntregaReservada(
        id=gerado.id, posse=uuid4(), dados_cifrados=cifra.cifrar("teste@example.com", gerado)
    )

    class Entregas:
        async def reservar(self):
            return reserva

        async def iniciar(self, recebida):
            assert recebida is reserva
            return True

        async def concluir(self, recebida, resultado, aguardar_segundos=None):
            assert recebida is reserva and resultado == "enviada"
            self.concluida = True

    cliente = MagicMock()
    monkeypatch.setattr(smtplib, "SMTP", MagicMock(return_value=cliente))
    repo = Entregas()
    async with fabrica_envio.criar_servico_email(configurar()) as envio:
        assert await ProcessarEmails(repo, cifra, envio).executar_uma()
    assert repo.concluida
    cliente.send_message.assert_called_once()


async def test_desafio_expirado_nao_abre_socket(monkeypatch):
    construir = MagicMock()
    monkeypatch.setattr(smtplib, "SMTP", construir)
    gerado = desafio().model_copy(update={"expira_em": agora_utc() - timedelta(seconds=1)})
    with pytest.raises(EnvioEmailPermanente):
        await EnvioEmailSMTPLocal(configurar()).enviar_verificacao("teste@example.com", gerado)
    construir.assert_not_called()
