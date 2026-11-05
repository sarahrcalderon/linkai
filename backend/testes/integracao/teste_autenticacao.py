import asyncio
import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from aplicacao.configuracao import Configuracao
from aplicacao.dominio.usuario import Usuario, agora_utc
from aplicacao.infraestrutura.modelos import ModeloSessao, ModeloUsuario
from aplicacao.infraestrutura.repositorio_usuarios import RepositorioUsuariosSQLAlchemy
from aplicacao.principal import criar_aplicacao

pytestmark = pytest.mark.postgres
SENHA_TESTE = "Frase longa de teste!"


@pytest_asyncio.fixture
async def ambiente_autenticacao(request):
    url = os.getenv("URL_BANCO_TESTE")
    if not url:
        pytest.skip("Configure URL_BANCO_TESTE para homologar autenticação.")
    ajustes = getattr(request, "param", {})
    configuracao = Configuracao(_env_file=None, url_banco=url, login_limite_tentativas=3, **ajustes)
    app = criar_aplicacao(configuracao)
    esquema = "teste_autenticacao_" + uuid4().hex

    def migrar(conexao):
        configuracao_alembic = Config(str(Path(__file__).parents[2] / "alembic.ini"))
        configuracao_alembic.attributes["connection"] = conexao
        command.upgrade(configuracao_alembic, "head")

    async with app.router.lifespan_context(app):
        banco = app.state.banco
        try:
            async with banco.motor.begin() as conexao:
                await conexao.execute(text(f'CREATE SCHEMA "{esquema}"'))
                await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
                await conexao.run_sync(migrar)
            banco.sessoes = async_sessionmaker(
                banco.motor.execution_options(schema_translate_map={None: esquema}),
                expire_on_commit=False,
            )
            usuario = Usuario(
                nome="Ana",
                email="ana@example.com",
                email_verificado=True,
                senha_hash=await app.state.hash_senha.gerar(SENHA_TESTE),
            )
            async with banco.transacao() as sessao:
                await RepositorioUsuariosSQLAlchemy(sessao).adicionar(usuario)
            transporte = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(
                transport=transporte,
                base_url="https://api.example.com",
                headers={"Origin": configuracao.origens_permitidas[0]},
            ) as cliente:
                yield app, cliente, banco, esquema, usuario
        finally:
            async with banco.motor.begin() as conexao:
                await conexao.execute(text(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE'))


async def entrar(cliente, **alteracoes):
    return await cliente.post(
        "/api/autenticacao/login",
        json={
            "email": " ANA@EXAMPLE.COM ",
            "senha": SENHA_TESTE,
            **alteracoes,
        },
    )


async def quantidade_sessoes(banco):
    async with banco.sessoes() as sessao:
        return await sessao.scalar(select(func.count()).select_from(ModeloSessao))


async def test_login_me_persistencia_e_segredos(ambiente_autenticacao, caplog):
    app, cliente, banco, _, usuario = ambiente_autenticacao
    resposta = await entrar(cliente)
    assert resposta.status_code == 200
    token = resposta.cookies["linkai_sessao"]
    cookie = resposta.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/api" in cookie
    assert "Max-Age=28800" in cookie and "expires=" in cookie
    assert "Domain=" not in cookie
    assert resposta.headers["cache-control"] == "no-store"
    assert resposta.json()["usuario"] == {
        "id": str(usuario.id),
        "nome": "Ana",
        "email": "ana@example.com",
        "email_verificado": True,
    }
    assert set(resposta.json()) == {"usuario", "csrf"}
    csrf = resposta.json()["csrf"]
    assert app.state.tokens.verificar_csrf(token, csrf)
    async with banco.sessoes() as sessao:
        persistida = await sessao.scalar(select(ModeloSessao))
        assert persistida.token_hash == app.state.tokens.resumir(token)
        assert persistida.token_hash != token
        assert persistida.usuario_id == usuario.id
        assert persistida.expira_em > agora_utc() and persistida.revogado_em is None
        for segredo in (token, persistida.token_hash, usuario.senha_hash, SENHA_TESTE):
            assert segredo not in resposta.text + caplog.text
    consulta = await cliente.get("/api/usuarios/me")
    assert consulta.status_code == 200 and consulta.json() == resposta.json()
    assert consulta.headers["cache-control"] == "no-store"
    assert "set-cookie" not in consulta.headers
    assert csrf not in caplog.text


@pytest.mark.parametrize("cenario", ["senha", "ausente", "nao_verificado", "inativo"])
async def test_rejeicoes_sao_genericas(ambiente_autenticacao, cenario):
    _, cliente, banco, _, usuario = ambiente_autenticacao
    alteracoes = {}
    if cenario == "senha":
        alteracoes["senha"] = "senha incorreta"
    elif cenario == "ausente":
        alteracoes["email"] = "ausente@example.com"
    else:
        async with banco.transacao() as sessao:
            await sessao.execute(
                update(ModeloUsuario)
                .where(ModeloUsuario.id == usuario.id)
                .values(
                    **({"ativo": False} if cenario == "inativo" else {"email_verificado": False})
                )
            )
    resposta = await entrar(cliente, **alteracoes)
    assert resposta.status_code == 401
    assert resposta.json() == {
        "erro": {"codigo": "credenciais_invalidas", "mensagem": "E-mail ou senha inválidos."}
    }
    assert "set-cookie" not in resposta.headers
    assert await quantidade_sessoes(banco) == 0


async def test_cadastro_continua_nao_verificado(ambiente_autenticacao):
    _, cliente, banco, _, _ = ambiente_autenticacao
    cadastro = await cliente.post(
        "/api/autenticacao/cadastro",
        json={
            "nome": "Bia",
            "email": "bia@example.com",
            "senha": SENHA_TESTE,
        },
    )
    assert cadastro.status_code == 202
    resposta = await entrar(cliente, email="bia@example.com")
    assert resposta.status_code == 401
    assert await quantidade_sessoes(banco) == 0


@pytest.mark.parametrize(
    "cenario",
    [
        "sem_cookie",
        "inexistente",
        "malformado",
        "expirado",
        "revogado",
        "inativo",
        "nao_verificado",
    ],
)
async def test_me_rejeita_sessoes_invalidas(ambiente_autenticacao, cenario):
    app, cliente, banco, _, usuario = ambiente_autenticacao
    if cenario == "inexistente":
        cliente.cookies.set("linkai_sessao", app.state.tokens.gerar(), path="/api")
    elif cenario == "malformado":
        cliente.cookies.set("linkai_sessao", "token_invalido", path="/api")
    elif cenario != "sem_cookie":
        assert (await entrar(cliente)).status_code == 200
        async with banco.transacao() as sessao:
            if cenario in {"inativo", "nao_verificado"}:
                await sessao.execute(
                    update(ModeloUsuario)
                    .where(ModeloUsuario.id == usuario.id)
                    .values(
                        **(
                            {"ativo": False}
                            if cenario == "inativo"
                            else {"email_verificado": False}
                        )
                    )
                )
            else:
                valores = (
                    {"revogado_em": agora_utc()}
                    if cenario == "revogado"
                    else {
                        "criado_em": agora_utc() - timedelta(hours=2),
                        "expira_em": agora_utc() - timedelta(hours=1),
                    }
                )
                await sessao.execute(update(ModeloSessao).values(**valores))
    resposta = await cliente.get("/api/usuarios/me")
    assert resposta.status_code == 401
    assert resposta.json()["erro"]["codigo"] == "sessao_invalida"


async def test_logout_revoga_cookie_e_idempotencia(ambiente_autenticacao):
    _, cliente, banco, _, _ = ambiente_autenticacao
    login = await entrar(cliente)
    token = login.cookies["linkai_sessao"]
    csrf = login.json()["csrf"]
    resposta = await cliente.post("/api/autenticacao/logout", headers={"X-CSRF-Token": csrf})
    assert resposta.status_code == 204 and resposta.content == b""
    assert "Max-Age=0" in resposta.headers["set-cookie"]
    assert "HttpOnly" in resposta.headers["set-cookie"]
    async with banco.sessoes() as sessao:
        assert (await sessao.scalar(select(ModeloSessao))).revogado_em is not None
    assert (await cliente.get("/api/usuarios/me")).status_code == 401
    assert (await cliente.post("/api/autenticacao/logout")).status_code == 204
    cliente.cookies.set("linkai_sessao", token, path="/api")
    assert (await cliente.get("/api/usuarios/me")).status_code == 401
    assert (
        await cliente.post("/api/autenticacao/logout", headers={"X-CSRF-Token": csrf})
    ).status_code == 204


@pytest.mark.parametrize("cenario", ["ausente", "errado", "outra_sessao", "origem"])
async def test_csrf_bloqueia_logout(ambiente_autenticacao, cenario):
    app, cliente, banco, _, _ = ambiente_autenticacao
    login = await entrar(cliente)
    csrf = login.json()["csrf"]
    cabecalhos = {}
    if cenario == "errado":
        cabecalhos["X-CSRF-Token"] = "a" * 64
    elif cenario == "outra_sessao":
        cabecalhos["X-CSRF-Token"] = app.state.tokens.gerar_csrf(app.state.tokens.gerar())
    elif cenario == "origem":
        cabecalhos = {"Origin": "https://malicioso.example.com", "X-CSRF-Token": csrf}
    resposta = await cliente.post("/api/autenticacao/logout", headers=cabecalhos)
    assert resposta.status_code == 403
    assert "set-cookie" not in resposta.headers
    assert (await cliente.get("/api/usuarios/me")).status_code == 200
    async with banco.sessoes() as sessao:
        assert (await sessao.scalar(select(ModeloSessao))).revogado_em is None


async def test_origin_cors_e_login_csrf(ambiente_autenticacao):
    _, cliente, banco, _, _ = ambiente_autenticacao
    preflight = await cliente.options(
        "/api/autenticacao/logout",
        headers={
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-CSRF-Token",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert preflight.headers["access-control-allow-credentials"] == "true"
    rejeitada = await cliente.post(
        "/api/autenticacao/login",
        json={
            "email": "ana@example.com",
            "senha": SENHA_TESTE,
        },
        headers={"Origin": "https://malicioso.example.com"},
    )
    assert rejeitada.status_code == 403
    assert "access-control-allow-origin" not in rejeitada.headers
    cliente.headers.pop("Origin")
    assert (await entrar(cliente)).status_code == 403
    assert await quantidade_sessoes(banco) == 0


async def test_login_limite_independente_do_cadastro(ambiente_autenticacao):
    _, cliente, banco, _, _ = ambiente_autenticacao
    for _ in range(3):
        assert (await entrar(cliente, senha="incorreta")).status_code == 401
    resposta = await entrar(cliente)
    assert resposta.status_code == 429 and int(resposta.headers["retry-after"]) > 0
    assert await quantidade_sessoes(banco) == 0
    assert (await cliente.post("/api/autenticacao/cadastro", json={})).status_code == 422


async def test_rotacao_contra_fixacao(ambiente_autenticacao):
    app, cliente, banco, _, _ = ambiente_autenticacao
    fixado = app.state.tokens.gerar()
    cliente.cookies.set("linkai_sessao", fixado, domain="api.example.com", path="/api")
    primeira = await entrar(cliente)
    antigo = primeira.cookies["linkai_sessao"]
    assert antigo != fixado
    segunda = await entrar(cliente)
    novo = segunda.cookies["linkai_sessao"]
    assert novo != antigo
    async with banco.sessoes() as sessao:
        anterior = await sessao.scalar(
            select(ModeloSessao).where(ModeloSessao.token_hash == app.state.tokens.resumir(antigo))
        )
        assert anterior.revogado_em is not None
    consulta = await cliente.get("/api/usuarios/me", headers={"Cookie": f"linkai_sessao={antigo}"})
    assert consulta.status_code == 401


async def test_logins_e_logouts_concorrentes(ambiente_autenticacao):
    _, cliente, banco, _, _ = ambiente_autenticacao
    respostas = await asyncio.gather(entrar(cliente), entrar(cliente))
    assert [resposta.status_code for resposta in respostas] == [200, 200]
    assert respostas[0].cookies["linkai_sessao"] != respostas[1].cookies["linkai_sessao"]
    assert await quantidade_sessoes(banco) == 2
    cabecalhos = {
        "Cookie": "linkai_sessao=" + respostas[0].cookies["linkai_sessao"],
        "X-CSRF-Token": respostas[0].json()["csrf"],
    }
    logouts = await asyncio.gather(
        *[cliente.post("/api/autenticacao/logout", headers=cabecalhos) for _ in range(2)]
    )
    assert [resposta.status_code for resposta in logouts] == [204, 204]
    async with banco.sessoes() as sessao:
        assert (
            await sessao.scalar(
                select(func.count())
                .select_from(ModeloSessao)
                .where(ModeloSessao.revogado_em.is_not(None))
            )
            == 1
        )


@pytest.mark.parametrize(
    "ambiente_autenticacao",
    [
        {
            "ambiente": "producao",
            "sessao_cookie_samesite": "none",
            "origens_permitidas": ["https://app.example.com"],
        }
    ],
    indirect=True,
)
async def test_cookie_producao_https_host_only(ambiente_autenticacao):
    _, cliente, _, _, _ = ambiente_autenticacao
    login = await entrar(cliente)
    assert login.status_code == 200
    assert "__Host-linkai_sessao=" in login.headers["set-cookie"]
    assert "Secure" in login.headers["set-cookie"] and "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=none" in login.headers["set-cookie"]
    assert "Domain=" not in login.headers["set-cookie"] and "Path=/;" in login.headers["set-cookie"]
    assert (await cliente.get("/api/usuarios/me")).status_code == 200
    saida = await cliente.post(
        "/api/autenticacao/logout", headers={"X-CSRF-Token": login.json()["csrf"]}
    )
    assert saida.status_code == 204
    assert "Secure" in saida.headers["set-cookie"] and "Max-Age=0" in saida.headers["set-cookie"]


async def test_falha_commit_login_nao_entrega_cookie_e_preserva_sessao(ambiente_autenticacao):
    app, cliente, banco, esquema, _ = ambiente_autenticacao
    async with banco.motor.begin() as conexao:
        await conexao.execute(
            text(
                f'ALTER TABLE "{esquema}".sessoes ADD CONSTRAINT usuario_unico_teste '
                "UNIQUE (usuario_id) DEFERRABLE INITIALLY DEFERRED"
            )
        )
    primeira = await entrar(cliente)
    antigo = primeira.cookies["linkai_sessao"]
    segunda = await entrar(cliente)
    assert segunda.status_code == 503
    assert "set-cookie" not in segunda.headers
    assert await quantidade_sessoes(banco) == 1
    async with banco.sessoes() as sessao:
        persistida = await sessao.scalar(select(ModeloSessao))
        assert persistida.token_hash == app.state.tokens.resumir(antigo)
        assert persistida.revogado_em is None
    assert (await cliente.get("/api/usuarios/me")).status_code == 200


async def test_falha_revogacao_nao_apaga_cookie(ambiente_autenticacao):
    _, cliente, banco, esquema, _ = ambiente_autenticacao
    login = await entrar(cliente)
    async with banco.motor.begin() as conexao:
        await conexao.execute(
            text(
                f'ALTER TABLE "{esquema}".sessoes ADD CONSTRAINT impedir_revogacao_teste '
                "CHECK (revogado_em IS NULL)"
            )
        )
    resposta = await cliente.post(
        "/api/autenticacao/logout", headers={"X-CSRF-Token": login.json()["csrf"]}
    )
    assert resposta.status_code == 503
    assert "set-cookie" not in resposta.headers
    assert (await cliente.get("/api/usuarios/me")).status_code == 200
    async with banco.sessoes() as sessao:
        assert (await sessao.scalar(select(ModeloSessao))).revogado_em is None


async def test_infraestrutura_sessao_indisponivel_falha_fechada(ambiente_autenticacao, caplog):
    _, cliente, banco, esquema, usuario = ambiente_autenticacao
    login = await entrar(cliente)
    token = login.cookies["linkai_sessao"]
    csrf = login.json()["csrf"]
    async with banco.motor.begin() as conexao:
        await conexao.execute(text(f'ALTER TABLE "{esquema}".sessoes RENAME TO sessoes_fora'))
    try:
        respostas = [
            await cliente.get("/api/usuarios/me"),
            await entrar(cliente),
            await cliente.post("/api/autenticacao/logout", headers={"X-CSRF-Token": csrf}),
        ]
        for resposta in respostas:
            assert resposta.status_code == 503
            assert resposta.json()["erro"]["codigo"] == "servico_indisponivel"
            assert "set-cookie" not in resposta.headers
            assert "SELECT" not in resposta.text and "Traceback" not in resposta.text
            for segredo in (token, csrf, usuario.senha_hash, SENHA_TESTE):
                assert segredo not in resposta.text + caplog.text
    finally:
        async with banco.motor.begin() as conexao:
            await conexao.execute(text(f'ALTER TABLE "{esquema}".sessoes_fora RENAME TO sessoes'))
    assert (await cliente.get("/api/usuarios/me")).status_code == 200


@pytest.mark.parametrize(
    "dados",
    [
        {},
        {"email": "invalido", "senha": SENHA_TESTE},
        {"email": "ana@example.com", "senha": "a" * 129},
        {"email": "ana@example.com", "senha": SENHA_TESTE, "email_verificado": True},
    ],
)
async def test_login_valida_entrada_sem_refletir_segredos(ambiente_autenticacao, dados):
    _, cliente, banco, _, _ = ambiente_autenticacao
    resposta = await cliente.post("/api/autenticacao/login", json=dados)
    assert resposta.status_code == 422
    assert SENHA_TESTE not in resposta.text
    assert "input" not in resposta.text and "set-cookie" not in resposta.headers
    assert await quantidade_sessoes(banco) == 0


async def test_login_limita_corpo(ambiente_autenticacao):
    _, cliente, banco, _, _ = ambiente_autenticacao
    resposta = await cliente.post("/api/autenticacao/login", content=b"a" * 8193)
    assert resposta.status_code == 413
    assert await quantidade_sessoes(banco) == 0
