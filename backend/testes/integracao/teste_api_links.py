import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text

from aplicacao.dominio.sessao import Sessao
from aplicacao.dominio.usuario import Usuario, agora_utc
from aplicacao.infraestrutura.modelos import ModeloLink
from aplicacao.infraestrutura.repositorio_sessoes import RepositorioSessoesSQLAlchemy
from aplicacao.infraestrutura.repositorio_usuarios import RepositorioUsuariosSQLAlchemy
from aplicacao.infraestrutura.tokens import TokensSeguros
from testes.integracao.teste_cadastro import ambiente_cadastro as ambiente_cadastro

pytestmark = pytest.mark.postgres


@pytest_asyncio.fixture
async def ambiente_links(ambiente_cadastro):
    cliente, banco, esquema = ambiente_cadastro
    tokens = TokensSeguros()
    cabecalhos = []
    async with banco.transacao() as s:
        for i in range(2):
            usuario = Usuario(
                nome="Pessoa",
                email=f"pessoa{i}@example.com",
                senha_hash="hash-fixture",
                email_verificado=True,
            )
            await RepositorioUsuariosSQLAlchemy(s).adicionar(usuario)
            token = tokens.gerar()
            await RepositorioSessoesSQLAlchemy(s).adicionar(
                Sessao(
                    usuario_id=usuario.id,
                    token_hash=tokens.resumir(token),
                    expira_em=agora_utc() + timedelta(hours=1),
                )
            )
            cabecalhos.append(
                {
                    "Cookie": f"linkai_sessao={token}",
                    "X-CSRF-Token": tokens.gerar_csrf(token),
                    "Origin": "http://localhost:5173",
                }
            )
    return cliente, banco, esquema, cabecalhos


def dados(**ajustes):
    return (
        dict(
            nome=" Campanha ",
            slug=" Campanha ",
            numero_whatsapp="+55 (11) 99999-9999",
            mensagem="Olá!",
        )
        | ajustes
    )


async def test_criar_consultar_listar_patch_e_excluir(ambiente_links):
    c, banco, _, h = ambiente_links
    resposta = await c.post("/api/links", json=dados(), headers=h[0])
    assert resposta.status_code == 201
    saida = resposta.json()
    assert set(saida) == {
        "id",
        "nome",
        "slug",
        "numero_whatsapp",
        "mensagem",
        "ativo",
        "criado_em",
        "atualizado_em",
    }
    assert saida["slug"] == "campanha" and saida["numero_whatsapp"] == "+5511999999999"
    assert resposta.headers["Cache-Control"] == "no-store"
    url = "/api/links/" + saida["id"]
    assert (await c.get(url, headers=h[0])).json() == saida
    atualizado = await c.patch(
        url, json={"mensagem": None, "slug": "Novo-Slug", "ativo": False}, headers=h[0]
    )
    assert atualizado.status_code == 200
    atual = atualizado.json()
    assert atual["nome"] == saida["nome"] and atual["numero_whatsapp"] == saida["numero_whatsapp"]
    assert atual["mensagem"] is None and atual["slug"] == "novo-slug" and not atual["ativo"]
    assert atual["atualizado_em"] > saida["atualizado_em"]
    assert (await c.patch(url, json={"ativo": True}, headers=h[0])).json()["ativo"]
    assert (await c.delete(url, headers=h[0])).status_code == 204
    for metodo, corpo in [("GET", None), ("PATCH", {"nome": "Outro"}), ("DELETE", None)]:
        assert (await c.request(metodo, url, json=corpo, headers=h[0])).status_code == 404
    assert (await c.get("/api/links", headers=h[0])).json()["total"] == 0
    assert (
        await c.post("/api/links", json=dados(slug="novo-slug"), headers=h[1])
    ).status_code == 409
    async with banco.transacao() as s:
        registro = await s.scalar(select(ModeloLink))
        assert registro.excluido_em is not None and not registro.ativo


@pytest.mark.parametrize(
    "ajuste",
    [
        {"usuario_id": str(uuid4())},
        {"id": str(uuid4())},
        {"criado_em": "2026-01-01"},
        {"ativo": True},
        {"slug": "api"},
        {"nome": "a"},
        {"numero_whatsapp": "abc"},
        {"mensagem": "<b>HTML</b>"},
        {"mensagem": "x" * 2001},
    ],
)
async def test_criacao_invalida(ambiente_links, ajuste):
    c, _, _, h = ambiente_links
    r = await c.post("/api/links", json=dados(**ajuste), headers=h[0])
    assert r.status_code == 422 and r.json()["erro"]["codigo"] == "dados_invalidos"


async def test_idor_e_paginacao_estavel(ambiente_links):
    c, _, _, h = ambiente_links
    ids = []
    for i in range(3):
        r = await c.post("/api/links", json=dados(slug=f"campanha-{i}"), headers=h[0])
        ids.append(r.json()["id"])
    for pagina in [1, 2, 3]:
        r = await c.get(f"/api/links?pagina={pagina}&tamanho=1", headers=h[0])
        assert r.json()["total"] == 3 and r.json()["itens"][0]["id"] == ids[-pagina]
    assert (await c.get("/api/links", headers=h[1])).json()["itens"] == []
    for identificador in [ids[0], str(uuid4())]:
        for metodo, corpo in [("GET", None), ("PATCH", {"nome": "Alterado"}), ("DELETE", None)]:
            r = await c.request(metodo, "/api/links/" + identificador, json=corpo, headers=h[1])
            assert r.status_code == 404 and r.json()["erro"]["codigo"] == "link_nao_encontrado"
    for consulta in ["pagina=0", "tamanho=101", "pagina=abc", "tamanho=0"]:
        assert (await c.get("/api/links?" + consulta, headers=h[0])).status_code == 422
    assert (await c.get("/api/links/invalido", headers=h[0])).status_code == 422


async def test_sessao_e_csrf_em_todas_operacoes(ambiente_links):
    c, _, _, h = ambiente_links
    link = (await c.post("/api/links", json=dados(), headers=h[0])).json()
    for metodo, url, corpo in [
        ("POST", "/api/links", dados()),
        ("GET", "/api/links", None),
        ("GET", "/api/links/" + link["id"], None),
        ("PATCH", "/api/links/" + link["id"], {"ativo": False}),
        ("DELETE", "/api/links/" + link["id"], None),
    ]:
        assert (await c.request(metodo, url, json=corpo)).status_code == 401
        if metodo in {"POST", "PATCH", "DELETE"}:
            for csrf in [None, "a" * 64]:
                headers = {k: v for k, v in h[0].items() if k != "X-CSRF-Token"}
                if csrf:
                    headers["X-CSRF-Token"] = csrf
                assert (
                    await c.request(metodo, url, json=corpo, headers=headers)
                ).status_code == 403
            assert (
                await c.request(
                    metodo, url, json=corpo, headers=h[0] | {"Origin": "https://hostil.example"}
                )
            ).status_code == 403


async def test_concorrencia_e_conflito_patch(ambiente_links):
    c, banco, _, h = ambiente_links
    resultados = await asyncio.gather(
        *(c.post("/api/links", json=dados(), headers=headers) for headers in h)
    )
    assert sorted(r.status_code for r in resultados) == [201, 409]
    vencedor = next(i for i, r in enumerate(resultados) if r.status_code == 201)
    outro = (await c.post("/api/links", json=dados(slug="outro-slug"), headers=h[vencedor])).json()
    r = await c.patch(
        "/api/links/" + outro["id"],
        json={"slug": "campanha", "nome": "Nao persistir"},
        headers=h[vencedor],
    )
    assert r.status_code == 409
    assert (await c.get("/api/links/" + outro["id"], headers=h[vencedor])).json()[
        "nome"
    ] == "Campanha"
    await asyncio.gather(
        c.patch("/api/links/" + outro["id"], json={"nome": "Alterado"}, headers=h[vencedor]),
        c.patch("/api/links/" + outro["id"], json={"mensagem": "Texto novo"}, headers=h[vencedor]),
    )
    atual = (await c.get("/api/links/" + outro["id"], headers=h[vencedor])).json()
    assert atual["nome"] == "Alterado" and atual["mensagem"] == "Texto novo"
    async with banco.transacao() as s:
        assert await s.scalar(select(func.count()).select_from(ModeloLink)) == 2


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"nome": None},
        {"slug": None},
        {"ativo": "false"},
        {"usuario_id": str(uuid4())},
        {"excluido_em": None},
    ],
)
async def test_patch_invalido(ambiente_links, payload):
    c, _, _, h = ambiente_links
    link = (await c.post("/api/links", json=dados(), headers=h[0])).json()
    assert (
        await c.patch("/api/links/" + link["id"], json=payload, headers=h[0])
    ).status_code == 422


async def test_limite_corpo_e_rollback_commit(ambiente_links):
    c, banco, esquema, h = ambiente_links

    async def partes():
        yield b'{"mensagem":"' + b"x" * 17000
        yield b'"}'

    r = await c.post(
        "/api/links", content=partes(), headers=h[0] | {"Content-Type": "application/json"}
    )
    assert r.status_code == 413
    async with banco.motor.begin() as conexao:
        await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
        await conexao.execute(
            text(
                "CREATE FUNCTION falhar_links() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'falha controlada'; END $$"
            )
        )
        await conexao.execute(
            text(
                "CREATE CONSTRAINT TRIGGER falha_links AFTER INSERT ON links "
                "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION falhar_links()"
            )
        )
    r = await c.post("/api/links", json=dados(), headers=h[0])
    assert r.status_code == 503 and r.json()["erro"]["codigo"] == "servico_indisponivel"
    async with banco.transacao() as s:
        assert await s.scalar(select(func.count()).select_from(ModeloLink)) == 0


async def test_cors_escrita_restrito(ambiente_links):
    c, _, _, _ = ambiente_links
    for metodo in ["PATCH", "DELETE"]:
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": metodo,
            "Access-Control-Request-Headers": "X-CSRF-Token, Content-Type",
        }
        resposta = await c.options("/api/links/" + str(uuid4()), headers=headers)
        assert resposta.status_code == 200
        assert resposta.headers["Access-Control-Allow-Origin"] == "http://localhost:5173"
        hostil = await c.options(
            "/api/links", headers=headers | {"Origin": "https://hostil.example"}
        )
        assert hostil.status_code == 400 and "Access-Control-Allow-Origin" not in hostil.headers
