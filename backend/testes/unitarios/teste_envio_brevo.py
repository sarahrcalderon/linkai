import asyncio
import json
from datetime import timedelta
from email.utils import format_datetime
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from aplicacao.casos_de_uso.contratos_verificacao import DesafioGerado, ServicoEnvioEmail
from aplicacao.casos_de_uso.erros_envio_email import (
    ConfiguracaoEnvioInvalida,
    EnvioEmailIndeterminado,
    EnvioEmailPermanente,
    EnvioEmailTemporario,
)
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura.brevo.configuracao import ConfiguracaoBrevo
from aplicacao.infraestrutura.brevo.envio import URL_ENVIO, EnvioEmailBrevo, ler_retry_after
from aplicacao.infraestrutura.brevo.fabrica import criar_envio_brevo
from aplicacao.infraestrutura.brevo.template import montar_template

CHAVE = "chave-privada-ficticia-do-teste"
CODIGO = "012345"
DESTINATARIO = "pessoa@example.com"


@pytest.fixture
def desafio():
    return DesafioGerado(
        id=uuid4(), usuario_id=uuid4(), codigo=CODIGO, expira_em=agora_utc() + timedelta(minutes=10)
    )


def configurar(**ajustes):
    return ConfiguracaoBrevo(
        _env_file=None, api_key=CHAVE, email_remetente="remetente@example.com", **ajustes
    )


async def test_envio_valido_payload_contrato_e_privacidade(desafio, caplog):
    caplog.set_level("DEBUG")
    requisicoes = []

    def responder(requisicao):
        requisicoes.append(requisicao)
        return httpx.Response(201, json={"messageId": "id-ficticio"})

    configuracao = configurar(nome_remetente="Equipe Linkai")
    async with criar_envio_brevo(configuracao, httpx.MockTransport(responder)) as adaptador:
        servico: ServicoEnvioEmail = adaptador
        assert await servico.enviar_verificacao(DESTINATARIO, desafio) is None
    assert len(requisicoes) == 1
    requisicao = requisicoes[0]
    assert str(requisicao.url) == URL_ENVIO and requisicao.url.scheme == "https"
    assert requisicao.headers["api-key"] == CHAVE
    assert requisicao.extensions["timeout"]["read"] == 10
    dados = json.loads(requisicao.content)
    assert dados["sender"] == {"email": "remetente@example.com", "name": "Equipe Linkai"}
    assert dados["to"] == [{"email": DESTINATARIO}]
    assert dados["subject"] == "Confirme seu e-mail — Linkai"
    assert dados["headers"]["idempotencyKey"] == str(desafio.id)
    assert CODIGO in dados["htmlContent"] and CODIGO in dados["textContent"]
    assert "senha" not in dados["htmlContent"] and "sessao" not in dados["textContent"]
    for segredo in (CHAVE, CODIGO, DESTINATARIO, dados["htmlContent"]):
        assert segredo not in caplog.text
    assert CHAVE not in repr(configuracao)


def test_template_escape_texto_e_sem_recursos_externos(desafio):
    mensagem = montar_template(desafio, '<img src="x" onerror="alert(1)">')
    html = mensagem.html.get_secret_value()
    assert "<img" not in html and "<script" not in html
    assert "&lt;img" in html
    assert "viewport" in html and 'width="100%"' in html
    assert "https://" not in html and "javascript:" not in html
    assert "UTC" in html and "única vez" in html
    assert "ignore esta mensagem" in mensagem.texto.get_secret_value()
    assert CODIGO not in repr(mensagem)


async def test_factory_sem_configuracao_falha_so_ao_ativar(monkeypatch):
    for nome in ("BREVO_API_KEY", "BREVO_EMAIL_REMETENTE"):
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setattr(
        ConfiguracaoBrevo, "model_config", ConfiguracaoBrevo.model_config | {"env_file": None}
    )
    with pytest.raises(ConfiguracaoEnvioInvalida):
        async with criar_envio_brevo():
            pytest.fail("Configuração ausente não deveria ativar envio.")


@pytest.mark.parametrize(
    "ajustes",
    [
        {"api_key": ""},
        {"api_key": "chave\nproibida"},
        {"email_remetente": "invalido"},
        {"timeout_segundos": 0},
        {"timeout_segundos": float("inf")},
        {"limite_tentativas": 0},
        {"tempo_total_segundos": 0},
        {"nome_remetente": " "},
    ],
)
def test_configuracao_invalida_sem_expor_segredos(ajustes):
    dados = {"api_key": CHAVE, "email_remetente": "remetente@example.com"} | ajustes
    with pytest.raises(ValidationError) as erro:
        ConfiguracaoBrevo(_env_file=None, **dados)
    assert CHAVE not in str(erro.value)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
async def test_4xx_permanente_nao_repete_nem_vaza_corpo(desafio, status, caplog):
    requisicoes = []

    def responder(requisicao):
        requisicoes.append(requisicao)
        return httpx.Response(status, json={"message": f"{CHAVE} {CODIGO} {DESTINATARIO}"})

    async with criar_envio_brevo(configurar(), httpx.MockTransport(responder)) as servico:
        with pytest.raises(EnvioEmailPermanente) as erro:
            await servico.enviar_verificacao(DESTINATARIO, desafio)
    assert len(requisicoes) == 1
    for segredo in (CHAVE, CODIGO, DESTINATARIO):
        assert segredo not in str(erro.value) + caplog.text


@pytest.mark.parametrize("status", [200, 202, 302, 408, 500, 502, 503, 504])
async def test_resposta_ambigua_sem_retentativa(desafio, status):
    requisicoes = []

    def responder(requisicao):
        requisicoes.append(requisicao)
        return httpx.Response(
            status,
            json={"messageId": "nao-confirmar"},
            headers={"Location": "https://outro.example.com"},
        )

    async with criar_envio_brevo(configurar(), httpx.MockTransport(responder)) as servico:
        with pytest.raises(EnvioEmailIndeterminado):
            await servico.enviar_verificacao(DESTINATARIO, desafio)
    assert len(requisicoes) == 1


@pytest.mark.parametrize("dados", [{}, {"messageId": ""}, {"messageId": None}, []])
async def test_201_incompleto_nao_confirma(desafio, dados):
    async with criar_envio_brevo(
        configurar(), httpx.MockTransport(lambda _: httpx.Response(201, json=dados))
    ) as servico:
        with pytest.raises(EnvioEmailIndeterminado):
            await servico.enviar_verificacao(DESTINATARIO, desafio)


async def test_201_json_invalido(desafio):
    async with criar_envio_brevo(
        configurar(), httpx.MockTransport(lambda _: httpx.Response(201, content=b"nao-json"))
    ) as servico:
        with pytest.raises(EnvioEmailIndeterminado):
            await servico.enviar_verificacao(DESTINATARIO, desafio)


@pytest.mark.parametrize(
    "falha", [httpx.ReadTimeout, httpx.WriteTimeout, httpx.ReadError, httpx.RemoteProtocolError]
)
async def test_falha_depois_de_envio_nao_repete(desafio, falha):
    requisicoes = []

    def responder(requisicao):
        requisicoes.append(requisicao)
        raise falha(f"{CHAVE} {CODIGO} {DESTINATARIO}")

    async with criar_envio_brevo(configurar(), httpx.MockTransport(responder)) as servico:
        with pytest.raises(EnvioEmailIndeterminado) as erro:
            await servico.enviar_verificacao(DESTINATARIO, desafio)
    assert len(requisicoes) == 1
    assert CHAVE not in str(erro.value) and CODIGO not in str(erro.value)


@pytest.mark.parametrize("falha", [httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout])
async def test_falha_antes_do_envio_tem_retentativas_limitadas(desafio, falha):
    requisicoes, esperas = [], []

    def responder(requisicao):
        requisicoes.append(requisicao)
        raise falha("Falha de teste")

    async def esperar(segundos):
        esperas.append(segundos)

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as cliente:
        servico = EnvioEmailBrevo(configurar(), cliente, esperar=esperar)
        with pytest.raises(EnvioEmailTemporario):
            await servico.enviar_verificacao(DESTINATARIO, desafio)
    assert len(requisicoes) == 3 and esperas == [0.5, 1.0]
    assert len({r.content for r in requisicoes}) == 1


async def test_429_retry_after_e_idempotencia_estavel(desafio):
    requisicoes, esperas = [], []

    def responder(requisicao):
        requisicoes.append(requisicao)
        if len(requisicoes) == 1:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(201, json={"messageId": "id-ficticio"})

    async def esperar(segundos):
        esperas.append(segundos)

    async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as cliente:
        servico = EnvioEmailBrevo(configurar(), cliente, esperar=esperar)
        await servico.enviar_verificacao(DESTINATARIO, desafio)
    assert len(requisicoes) == 2 and esperas == [2]
    assert requisicoes[0].content == requisicoes[1].content


@pytest.mark.parametrize("retry_after", ["30", "9" * 500])
async def test_retry_after_maior_que_orcamento_nao_e_encurtado(desafio, retry_after):
    requisicoes = []

    def responder(requisicao):
        requisicoes.append(requisicao)
        return httpx.Response(429, headers={"Retry-After": retry_after})

    async with criar_envio_brevo(configurar(), httpx.MockTransport(responder)) as servico:
        with pytest.raises(EnvioEmailTemporario):
            await servico.enviar_verificacao(DESTINATARIO, desafio)
    assert len(requisicoes) == 1


def test_retry_after_data_e_invalido():
    agora = agora_utc().replace(microsecond=0)
    data = format_datetime(agora + timedelta(seconds=3), usegmt=True)
    assert ler_retry_after(data, agora) == 3
    assert ler_retry_after("invalido", agora) is None
    assert ler_retry_after(None, agora) is None


async def test_limite_total_cancela_resposta_indeterminada(desafio):
    async def responder(_):
        await asyncio.sleep(1)
        return httpx.Response(201, json={"messageId": "tardio"})

    async with criar_envio_brevo(
        configurar(tempo_total_segundos=0.01), httpx.MockTransport(responder)
    ) as servico:
        with pytest.raises(EnvioEmailIndeterminado):
            await servico.enviar_verificacao(DESTINATARIO, desafio)


@pytest.mark.parametrize("status", [400, 409])
async def test_duplicata_nao_e_confirmacao(desafio, status):
    async with criar_envio_brevo(
        configurar(),
        httpx.MockTransport(lambda _: httpx.Response(status, json={"code": "duplicate_parameter"})),
    ) as servico:
        with pytest.raises(EnvioEmailIndeterminado):
            await servico.enviar_verificacao(DESTINATARIO, desafio)


async def test_destinatario_invalido_e_desafio_expirado_nao_chamam_api(desafio):
    requisicoes = []

    def responder(requisicao):
        requisicoes.append(requisicao)
        return httpx.Response(201, json={"messageId": "nao-deveria-enviar"})

    async with criar_envio_brevo(configurar(), httpx.MockTransport(responder)) as servico:
        with pytest.raises(EnvioEmailPermanente):
            await servico.enviar_verificacao("invalido", desafio)
        expirado = desafio.model_copy(update={"expira_em": agora_utc() - timedelta(seconds=1)})
        with pytest.raises(EnvioEmailTemporario):
            await servico.enviar_verificacao(DESTINATARIO, expirado)
    assert not requisicoes


async def test_contrato_falso_nao_exige_configuracao_brevo(desafio):
    class EnvioFalso:
        async def enviar_verificacao(self, destinatario: str, desafio: DesafioGerado) -> None:
            assert destinatario == DESTINATARIO

    servico: ServicoEnvioEmail = EnvioFalso()
    await servico.enviar_verificacao(DESTINATARIO, desafio)


async def test_429_persistente_respeita_limite_de_tentativas(desafio):
    requisicoes = []

    def responder(requisicao):
        requisicoes.append(requisicao)
        return httpx.Response(429, headers={"Retry-After": "0"})

    async with criar_envio_brevo(configurar(), httpx.MockTransport(responder)) as servico:
        with pytest.raises(EnvioEmailTemporario):
            await servico.enviar_verificacao(DESTINATARIO, desafio)
    assert len(requisicoes) == 3
