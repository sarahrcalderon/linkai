import asyncio
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import func, select, text, update

from aplicacao.casos_de_uso.erros_envio_email import EnvioEmailTemporario
from aplicacao.casos_de_uso.processar_emails import ProcessarEmails
from aplicacao.configuracao import Configuracao
from aplicacao.dominio.usuario import agora_utc
from aplicacao.infraestrutura.brevo.configuracao import ConfiguracaoBrevo
from aplicacao.infraestrutura.brevo.fabrica import criar_envio_brevo
from aplicacao.infraestrutura.cifra_outbox import CifraOutbox
from aplicacao.infraestrutura.modelos import (
    ModeloEntregaEmail,
    ModeloUsuario,
    ModeloVerificacaoEmail,
)
from aplicacao.infraestrutura.repositorio_entregas import RepositorioEntregasSQLAlchemy
from aplicacao.principal import criar_aplicacao
from testes.integracao.teste_cadastro import ambiente_cadastro as ambiente_cadastro

pytestmark = pytest.mark.postgres


async def cadastrar(cliente, email="ana@example.com"):
    return await cliente.post(
        "/api/autenticacao/cadastro",
        json={"nome": "Ana", "email": email, "senha": "Frase longa de teste!"},
    )


async def obter_entrega(banco):
    async with banco.sessoes() as sessao:
        return await sessao.scalar(
            select(ModeloEntregaEmail).order_by(ModeloEntregaEmail.criado_em.desc()).limit(1)
        )


async def obter_codigo(banco):
    entrega = await obter_entrega(banco)
    _, desafio = CifraOutbox(Configuracao().outbox_chave).decifrar(
        entrega.dados_cifrados, entrega.id
    )
    return desafio.codigo.get_secret_value()


async def confirmar(cliente, codigo, email="ana@example.com"):
    return await cliente.post(
        "/api/autenticacao/verificar-email", json={"email": email, "codigo": codigo}
    )


def montar_worker(banco, envio, **ajustes):
    configuracao = Configuracao(_env_file=None, **ajustes)
    repo = RepositorioEntregasSQLAlchemy(banco, configuracao)
    return ProcessarEmails(repo, CifraOutbox(configuracao.outbox_chave), envio), repo


class EnvioContado:
    def __init__(self):
        self.quantidade = 0

    async def enviar_verificacao(self, destinatario, desafio):
        self.quantidade += 1


async def test_cadastro_outbox_confirmacao_e_duplicata_verificada(ambiente_cadastro, caplog):
    cliente, banco, _ = ambiente_cadastro
    assert (await cadastrar(cliente)).status_code == 202
    codigo = await obter_codigo(banco)
    entrega = await obter_entrega(banco)
    assert entrega.estado == "pendente" and "ana@example.com" not in entrega.dados_cifrados
    assert codigo not in entrega.dados_cifrados + caplog.text
    assert (await confirmar(cliente, codigo)).status_code == 200
    resposta = await confirmar(cliente, codigo)
    assert resposta.status_code == 400 and "set-cookie" not in resposta.headers
    assert (await cadastrar(cliente)).status_code == 202
    async with banco.sessoes() as sessao:
        assert await sessao.scalar(select(func.count()).select_from(ModeloEntregaEmail)) == 1
        assert (await sessao.scalar(select(ModeloUsuario))).email_verificado
    envio = EnvioContado()
    worker, _ = montar_worker(banco, envio)
    await worker.executar_uma()
    assert envio.quantidade == 0 and (await obter_entrega(banco)).estado == "cancelada"


async def test_cadastro_concorrente_grava_unica_intencao(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    respostas = await asyncio.gather(cadastrar(cliente), cadastrar(cliente))
    assert [r.status_code for r in respostas] == [202, 202]
    assert respostas[0].json() == respostas[1].json()
    async with banco.sessoes() as sessao:
        for modelo in (ModeloUsuario, ModeloVerificacaoEmail, ModeloEntregaEmail):
            assert await sessao.scalar(select(func.count()).select_from(modelo)) == 1


async def test_confirmacoes_concorrentes_e_login_bloqueado_ate_codigo(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    await cadastrar(cliente)
    codigo = await obter_codigo(banco)
    dados = {"email": "ana@example.com", "senha": "Frase longa de teste!"}
    cabecalhos = {"Origin": "http://localhost:5173"}
    assert (
        await cliente.post("/api/autenticacao/login", json=dados, headers=cabecalhos)
    ).status_code == 401
    respostas = await asyncio.gather(confirmar(cliente, codigo), confirmar(cliente, codigo))
    assert sorted(r.status_code for r in respostas) == [200, 400]
    assert all("set-cookie" not in r.headers for r in respostas)
    assert (
        await cliente.post("/api/autenticacao/login", json=dados, headers=cabecalhos)
    ).status_code == 200


async def test_codigo_incorreto_expirado_e_nao_enumeracao(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    await cadastrar(cliente)
    codigo = await obter_codigo(banco)
    incorreto = "000000" if codigo != "000000" else "999999"
    existente = await confirmar(cliente, incorreto)
    inexistente = await confirmar(cliente, incorreto, "ausente@example.com")
    assert existente.status_code == inexistente.status_code == 400
    assert existente.json() == inexistente.json()
    async with banco.transacao() as sessao:
        await sessao.execute(
            update(ModeloVerificacaoEmail).values(
                criado_em=agora_utc() - timedelta(hours=2),
                expira_em=agora_utc() - timedelta(hours=1),
            )
        )
    assert (await confirmar(cliente, codigo)).status_code == 400


async def test_limite_de_tentativas_persiste(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    await cadastrar(cliente)
    codigo = await obter_codigo(banco)
    errado = "000000" if codigo != "000000" else "999999"
    for _ in range(5):
        assert (await confirmar(cliente, errado)).status_code == 400
    assert (await confirmar(cliente, codigo)).status_code == 400
    async with banco.sessoes() as sessao:
        assert (await sessao.scalar(select(ModeloVerificacaoEmail))).tentativas == 5
        assert not (await sessao.scalar(select(ModeloUsuario))).email_verificado


async def test_reenvio_cooldown_concorrencia_e_invalidacao(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    await cadastrar(cliente)
    antigo = await obter_codigo(banco)
    primeira = await cliente.post(
        "/api/autenticacao/reenviar-codigo", json={"email": "ana@example.com"}
    )
    ausente = await cliente.post(
        "/api/autenticacao/reenviar-codigo", json={"email": "ausente@example.com"}
    )
    assert primeira.status_code == ausente.status_code == 202 and primeira.json() == ausente.json()
    async with banco.sessoes() as sessao:
        assert await sessao.scalar(select(func.count()).select_from(ModeloEntregaEmail)) == 1
    async with banco.transacao() as sessao:
        await sessao.execute(
            update(ModeloVerificacaoEmail).values(criado_em=agora_utc() - timedelta(seconds=61))
        )
    respostas = await asyncio.gather(
        *[
            cliente.post("/api/autenticacao/reenviar-codigo", json={"email": "ana@example.com"})
            for _ in range(3)
        ]
    )
    assert all(r.status_code == 202 for r in respostas)
    async with banco.sessoes() as sessao:
        estados = list(await sessao.scalars(select(ModeloEntregaEmail.estado)))
        assert sorted(estados) == ["cancelada", "pendente"]
    assert (await confirmar(cliente, antigo)).status_code == 400
    assert (await confirmar(cliente, await obter_codigo(banco))).status_code == 200


async def test_falha_outbox_reverte_usuario_e_desafio(ambiente_cadastro):
    cliente, banco, esquema = ambiente_cadastro
    async with banco.motor.begin() as conexao:
        await conexao.execute(
            text(f'ALTER TABLE "{esquema}".outbox_email ADD CONSTRAINT falhar CHECK (false)')
        )
    assert (await cadastrar(cliente)).status_code == 503
    async with banco.sessoes() as sessao:
        for modelo in (ModeloUsuario, ModeloVerificacaoEmail, ModeloEntregaEmail):
            assert await sessao.scalar(select(func.count()).select_from(modelo)) == 0


async def test_limite_persistente_compartilhado_entre_apps(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    for _ in range(5):
        assert (await cliente.post("/api/autenticacao/cadastro", json={})).status_code == 422
    app = criar_aplicacao(Configuracao(_env_file=None))
    async with app.router.lifespan_context(app):
        app.state.banco = banco
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://teste",
        ) as outro:
            resposta = await outro.post("/api/autenticacao/cadastro", json={})
    assert resposta.status_code == 429 and "Retry-After" in resposta.headers


async def test_worker_envia_fora_da_transacao_e_remove_conteudo(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    await cadastrar(cliente)

    class EnvioSemTransacao(EnvioContado):
        async def enviar_verificacao(self, destinatario, desafio):
            async with banco.motor.connect() as conexao:
                quantidade = await conexao.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname=current_database() AND state='idle in transaction'"
                    )
                )
                assert quantidade == 0
            await super().enviar_verificacao(destinatario, desafio)

    envio = EnvioSemTransacao()
    worker, _ = montar_worker(banco, envio)
    assert await worker.executar_uma()
    assert envio.quantidade == 1
    entrega = await obter_entrega(banco)
    assert entrega.estado == "enviada" and entrega.dados_cifrados is None
    assert not await worker.executar_uma()


async def test_dois_workers_reservam_apenas_uma_vez(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    await cadastrar(cliente)
    envio = EnvioContado()
    primeiro, _ = montar_worker(banco, envio)
    segundo, _ = montar_worker(banco, envio)
    await asyncio.gather(primeiro.executar_uma(), segundo.executar_uma())
    assert envio.quantidade == 1 and (await obter_entrega(banco)).estado == "enviada"


@pytest.mark.parametrize("iniciou", [False, True])
async def test_worker_interrompido_recuperacao_e_fencing(ambiente_cadastro, iniciou):
    cliente, banco, _ = ambiente_cadastro
    await cadastrar(cliente)
    envio = EnvioContado()
    worker, repo = montar_worker(banco, envio)
    reserva = await repo.reservar()
    if iniciou:
        assert await repo.iniciar(reserva)
    async with banco.transacao() as sessao:
        await sessao.execute(
            update(ModeloEntregaEmail).values(arrendado_ate=agora_utc() - timedelta(seconds=1))
        )
    await worker.executar_uma()
    entrega = await obter_entrega(banco)
    assert envio.quantidade == (0 if iniciou else 1)
    assert entrega.estado == ("indeterminada" if iniciou else "enviada")
    assert entrega.dados_cifrados is None
    await repo.concluir(reserva, "enviada")
    assert (await obter_entrega(banco)).estado == entrega.estado


@pytest.mark.parametrize(
    "status,estado", [(201, "enviada"), (400, "falha"), (503, "indeterminada"), (429, "pendente")]
)
async def test_brevo_simulado_e_politica_outbox(ambiente_cadastro, status, estado):
    cliente, banco, _ = ambiente_cadastro
    await cadastrar(cliente)
    configuracao = ConfiguracaoBrevo(
        _env_file=None,
        api_key="chave-ficticia",
        email_remetente="remetente@example.com",
        limite_tentativas=1,
    )
    transporte = httpx.MockTransport(
        lambda _: httpx.Response(
            status, json={"messageId": "ficticio"}, headers={"Retry-After": "0"}
        )
    )
    async with criar_envio_brevo(configuracao, transporte) as envio:
        worker, _ = montar_worker(banco, envio)
        await worker.executar_uma()
    entrega = await obter_entrega(banco)
    assert entrega.estado == estado and entrega.tentativas == 1
    assert (entrega.dados_cifrados is not None) == (estado == "pendente")


async def test_backoff_retry_after_e_esgotamento(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    await cadastrar(cliente)

    class EnvioTemporario:
        async def enviar_verificacao(self, destinatario, desafio):
            raise EnvioEmailTemporario(aguardar_segundos=80)

    worker, _ = montar_worker(banco, EnvioTemporario(), outbox_limite_tentativas=2)
    await worker.executar_uma()
    entrega = await obter_entrega(banco)
    assert entrega.proxima_tentativa > agora_utc() + timedelta(seconds=75)
    async with banco.transacao() as sessao:
        await sessao.execute(update(ModeloEntregaEmail).values(proxima_tentativa=agora_utc()))
    await worker.executar_uma()
    entrega = await obter_entrega(banco)
    assert entrega.estado == "falha" and entrega.dados_cifrados is None and entrega.tentativas == 2


async def test_falha_no_commit_da_outbox_reverte_tudo(ambiente_cadastro):
    cliente, banco, esquema = ambiente_cadastro
    async with banco.motor.begin() as conexao:
        await conexao.execute(
            text(
                f'CREATE FUNCTION "{esquema}".falhar_outbox() RETURNS trigger '
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Falha controlada'; END $$"
            )
        )
        await conexao.execute(
            text(
                f'CREATE CONSTRAINT TRIGGER falha_commit AFTER INSERT ON "{esquema}".outbox_email '
                "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW "
                f'EXECUTE FUNCTION "{esquema}".falhar_outbox()'
            )
        )
    resposta = await cadastrar(cliente)
    assert resposta.status_code == 503 and "set-cookie" not in resposta.headers
    async with banco.sessoes() as sessao:
        for modelo in (ModeloUsuario, ModeloVerificacaoEmail, ModeloEntregaEmail):
            assert await sessao.scalar(select(func.count()).select_from(modelo)) == 0


async def test_cancelamento_durante_envio_nao_repete(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    await cadastrar(cliente)

    class EnvioInterrompido:
        async def enviar_verificacao(self, destinatario, desafio):
            raise asyncio.CancelledError()

    worker, _ = montar_worker(banco, EnvioInterrompido())
    with pytest.raises(asyncio.CancelledError):
        await worker.executar_uma()
    entrega = await obter_entrega(banco)
    assert entrega.estado == "indeterminada" and entrega.dados_cifrados is None
    assert not await worker.executar_uma()


async def test_origem_hostil_nao_enfileira_email(ambiente_cadastro):
    cliente, banco, _ = ambiente_cadastro
    resposta = await cliente.post(
        "/api/autenticacao/cadastro",
        headers={"Origin": "https://hostil.example"},
        json={"nome": "Ana", "email": "ana@example.com", "senha": "Frase longa de teste!"},
    )
    assert resposta.status_code == 403
    async with banco.sessoes() as sessao:
        assert await sessao.scalar(select(func.count()).select_from(ModeloEntregaEmail)) == 0
