import httpx
import pytest
from pydantic import SecretStr

from aplicacao.infraestrutura.brevo.configuracao import ConfiguracaoBrevo
from aplicacao.infraestrutura.brevo.fabrica import criar_envio_brevo
from testes.integracao.teste_cadastro import ambiente_cadastro as ambiente_cadastro
from testes.integracao.teste_fluxo_email import (
    cadastrar,
    confirmar,
    montar_worker,
    obter_entrega,
)

pytestmark = pytest.mark.postgres


async def test_cadastro_worker_falso_confirmacao_login_logout(ambiente_cadastro, caplog):
    cliente, banco, _ = ambiente_cadastro

    class CaixaFalsa:
        codigo: SecretStr | None = None

        async def enviar_verificacao(self, destinatario, desafio):
            self.codigo = desafio.codigo

    caixa = CaixaFalsa()
    dados = {"email": "ana@example.com", "senha": "Frase longa de teste!"}
    origem = {"Origin": "http://localhost:5173"}
    assert (await cadastrar(cliente)).status_code == 202
    assert (
        await cliente.post("/api/autenticacao/login", json=dados, headers=origem)
    ).status_code == 401
    worker, _ = montar_worker(banco, caixa)
    assert await worker.executar_uma()
    assert caixa.codigo is not None
    assert (await obter_entrega(banco)).dados_cifrados is None
    resposta = await confirmar(cliente, caixa.codigo.get_secret_value())
    assert resposta.status_code == 200 and "set-cookie" not in resposta.headers
    assert caixa.codigo.get_secret_value() not in resposta.text + caplog.text
    assert (await confirmar(cliente, caixa.codigo.get_secret_value())).status_code == 400
    login = await cliente.post("/api/autenticacao/login", json=dados, headers=origem)
    assert login.status_code == 200
    assert (await cliente.get("/api/usuarios/me")).status_code == 200
    assert (await cliente.post("/api/autenticacao/logout", headers=origem)).status_code == 403
    assert (
        await cliente.post(
            "/api/autenticacao/logout",
            headers={**origem, "X-CSRF-Token": login.json()["csrf"]},
        )
    ).status_code == 204
    assert (await cliente.get("/api/usuarios/me")).status_code == 401


@pytest.mark.parametrize(
    "falha,estado",
    [
        (httpx.ConnectError, "pendente"),
        (httpx.ConnectTimeout, "pendente"),
        (httpx.ReadTimeout, "indeterminada"),
        (httpx.WriteTimeout, "indeterminada"),
    ],
)
async def test_falhas_transporte_brevo_no_worker_postgresql(ambiente_cadastro, falha, estado):
    cliente, banco, _ = ambiente_cadastro
    assert (await cadastrar(cliente)).status_code == 202
    chamadas = 0

    def responder(requisicao):
        nonlocal chamadas
        chamadas += 1
        raise falha("Falha de transporte simulada.")

    configuracao = ConfiguracaoBrevo(
        _env_file=None,
        api_key="chave-ficticia",
        email_remetente="remetente@example.com",
        limite_tentativas=1,
    )
    async with criar_envio_brevo(configuracao, httpx.MockTransport(responder)) as envio:
        worker, _ = montar_worker(banco, envio)
        assert await worker.executar_uma()
        entrega = await obter_entrega(banco)
        assert entrega.estado == estado and entrega.tentativas == 1
        assert (entrega.dados_cifrados is not None) == (estado == "pendente")
        # Backoff ou quarentena: não inicia uma segunda chamada imediatamente.
        assert not await worker.executar_uma()
    assert chamadas == 1
