from dataclasses import replace
from urllib.parse import parse_qs, quote, urlsplit

import pytest
from sqlalchemy import event

from aplicacao.dominio.link import Link
from aplicacao.dominio.usuario import Usuario, agora_utc
from aplicacao.infraestrutura.repositorio_links import RepositorioLinksSQLAlchemy
from aplicacao.infraestrutura.repositorio_usuarios import RepositorioUsuariosSQLAlchemy
from testes.integracao.teste_cadastro import ambiente_cadastro as ambiente_cadastro

pytestmark = pytest.mark.postgres


async def persistir(banco, mensagem=None, **ajustes):
    usuario = Usuario(nome="Pessoa", email="pessoa@example.com", senha_hash="hash-fixture")
    link = Link(
        **(
            dict(
                usuario_id=usuario.id,
                nome="Campanha",
                slug="campanha",
                numero_whatsapp="+5511999999999",
                mensagem=mensagem,
            )
            | ajustes
        )
    )
    async with banco.transacao() as s:
        await RepositorioUsuariosSQLAlchemy(s).adicionar(usuario)
        await RepositorioLinksSQLAlchemy(s).adicionar(link)
    return link


@pytest.mark.parametrize(
    "mensagem",
    [
        None,
        "",
        "Texto com espaços",
        "Olá, ação e café",
        "🚀💬",
        "Linha 1\nLinha 2",
        "&text=x?url=https://hostil.example/#fragmento",
        "\r\nLocation: https://hostil.example",
    ],
)
async def test_302_publico_sem_cookies_ou_vazamento(ambiente_cadastro, mensagem, caplog):
    c, banco, _ = ambiente_cadastro
    link = await persistir(banco, mensagem)
    resposta = await c.get("/r/CAMPANHA", follow_redirects=False)
    assert resposta.status_code == 302 and resposta.content == b""
    assert resposta.headers["Cache-Control"] == "no-store, max-age=0"
    assert resposta.headers["Referrer-Policy"] == "no-referrer"
    assert "set-cookie" not in resposta.headers
    destino = urlsplit(resposta.headers["Location"])
    assert destino.scheme == "https" and destino.netloc == "wa.me"
    assert destino.path == "/5511999999999" and destino.fragment == ""
    assert parse_qs(destino.query) == ({"text": [mensagem]} if mensagem else {})
    assert str(link.usuario_id) not in resposta.text
    assert link.numero_whatsapp not in caplog.text and "5511999999999" not in caplog.text
    if mensagem:
        assert mensagem not in caplog.text


@pytest.mark.parametrize("estado", ["inativo", "excluido", "ausente"])
async def test_indisponiveis_mesmo_404(ambiente_cadastro, estado):
    c, banco, _ = ambiente_cadastro
    if estado != "ausente":
        link = await persistir(banco)
        async with banco.transacao() as s:
            await RepositorioLinksSQLAlchemy(s).atualizar(
                link.excluir()
                if estado == "excluido"
                else replace(link, ativo=False, atualizado_em=agora_utc())
            )
    resposta = await c.get("/r/campanha", follow_redirects=False)
    assert resposta.status_code == 404
    assert resposta.json() == {
        "erro": {"codigo": "link_nao_encontrado", "mensagem": "Link não encontrado."}
    }
    assert resposta.headers["Cache-Control"] == "no-store"
    assert "location" not in resposta.headers and "set-cookie" not in resposta.headers


@pytest.mark.parametrize(
    "slug",
    [
        "ab",
        "a" * 65,
        "api",
        "slug ruim",
        "ação",
        "https:hostil",
        "campanha\r\nLocation:malicioso",
        "https://hostil.example",
        "//hostil.example",
        "",
    ],
)
async def test_slug_invalido_sem_sql(ambiente_cadastro, slug):
    c, banco, _ = ambiente_cadastro
    consultas = []

    def contar(*args):
        consultas.append(True)

    event.listen(banco.motor.sync_engine, "before_cursor_execute", contar)
    try:
        resposta = await c.get("/r/" + quote(slug, safe=""), follow_redirects=False)
    finally:
        event.remove(banco.motor.sync_engine, "before_cursor_execute", contar)
    assert resposta.status_code == 404 and not consultas


async def test_destino_arbitrario_ignorado_e_slug_renomeado(ambiente_cadastro):
    c, banco, _ = ambiente_cadastro
    link = await persistir(banco)
    resposta = await c.get("/r/campanha?url=https://hostil.example", follow_redirects=False)
    assert resposta.headers["Location"] == "https://wa.me/5511999999999"
    async with banco.transacao() as s:
        await RepositorioLinksSQLAlchemy(s).atualizar(
            replace(link, slug="renomeado", atualizado_em=agora_utc())
        )
    assert (await c.get("/r/campanha", follow_redirects=False)).status_code == 404
    assert (await c.get("/r/renomeado", follow_redirects=False)).status_code == 302
    async with banco.transacao() as s:
        await RepositorioLinksSQLAlchemy(s).adicionar(
            Link(
                usuario_id=link.usuario_id,
                nome="Novo link",
                slug="campanha",
                numero_whatsapp="+441234567890",
            )
        )
    assert (await c.get("/r/campanha", follow_redirects=False)).headers[
        "Location"
    ] == "https://wa.me/441234567890"


async def test_falha_persistencia_sem_expor_detalhes(ambiente_cadastro, monkeypatch):
    c, _, _ = ambiente_cadastro

    async def falhar(*args):
        raise RuntimeError("Detalhes internos que não podem ser retornados.")

    monkeypatch.setattr(RepositorioLinksSQLAlchemy, "obter_publico_por_slug", falhar)
    resposta = await c.get("/r/campanha", follow_redirects=False)
    assert resposta.status_code == 503 and resposta.headers["Cache-Control"] == "no-store"
    assert "Detalhes internos" not in resposta.text and "location" not in resposta.headers
