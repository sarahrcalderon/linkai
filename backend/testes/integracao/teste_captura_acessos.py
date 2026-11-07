import asyncio
from dataclasses import fields, replace

import pytest
from sqlalchemy import func, select, text

from aplicacao.dominio.evento_acesso import EventoDeAcesso
from aplicacao.infraestrutura.modelos import ModeloEventoAcesso, ModeloLink
from aplicacao.infraestrutura.registro_acessos import PersistenciaEventoSQLAlchemy
from aplicacao.infraestrutura.repositorio_eventos_acesso import RepositorioEventosAcessoSQLAlchemy
from aplicacao.infraestrutura.repositorio_links import RepositorioLinksSQLAlchemy
from testes.integracao.teste_cadastro import ambiente_cadastro as ambiente_cadastro
from testes.integracao.teste_eventos_acesso import preparar_links

pytestmark = pytest.mark.postgres


async def quantidade(banco):
    async with banco.transacao() as s:
        return await s.scalar(select(func.count()).select_from(ModeloEventoAcesso))


async def test_homologacao_tres_gets_e_desativacao(ambiente_cadastro):
    c, banco, _ = ambiente_cadastro
    link, _ = await preparar_links(banco)
    assert await quantidade(banco) == 0
    for _ in range(3):
        r = await c.get("/r/" + link.slug, follow_redirects=False)
        assert r.status_code == 302 and r.headers["Location"] == "https://wa.me/5511999999999"
        assert r.headers["Cache-Control"] == "no-store, max-age=0" and "set-cookie" not in r.headers
        assert banco.motor.pool.checkedout() == 0
    assert await quantidade(banco) == 3
    async with banco.transacao() as s:
        await RepositorioLinksSQLAlchemy(s).atualizar(replace(link, ativo=False))
    assert (await c.get("/r/" + link.slug, follow_redirects=False)).status_code == 404
    assert await quantidade(banco) == 3
    assert {f.name for f in fields(EventoDeAcesso)} == {"id", "link_id", "acessado_em"}


@pytest.mark.parametrize("estado", ["ausente", "invalido", "inativo", "excluido"])
async def test_404_sem_evento(ambiente_cadastro, estado):
    c, banco, _ = ambiente_cadastro
    link, _ = await preparar_links(banco)
    if estado in {"inativo", "excluido"}:
        async with banco.transacao() as s:
            await RepositorioLinksSQLAlchemy(s).atualizar(
                link.excluir() if estado == "excluido" else replace(link, ativo=False)
            )
    slug = {"ausente": "nao-existe", "invalido": "api"}.get(estado, link.slug)
    assert (await c.get("/r/" + slug, follow_redirects=False)).status_code == 404
    assert await quantidade(banco) == 0


@pytest.mark.parametrize("adiada", [False, True])
async def test_falha_sql_isolada_no_flush_ou_commit_preserva_302(ambiente_cadastro, adiada, caplog):
    c, banco, esquema = ambiente_cadastro
    link, _ = await preparar_links(banco)
    async with banco.motor.begin() as conexao:
        await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
        await conexao.execute(
            text(
                "CREATE FUNCTION falhar_evento() RETURNS trigger LANGUAGE plpgsql AS $$ "
                "BEGIN RAISE EXCEPTION 'detalhes-privados'; END $$"
            )
        )
        sql = (
            "CREATE CONSTRAINT TRIGGER falha_evento AFTER INSERT ON eventos_acesso "
            "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION falhar_evento()"
            if adiada
            else "CREATE TRIGGER falha_evento BEFORE INSERT ON eventos_acesso "
            "FOR EACH ROW EXECUTE FUNCTION falhar_evento()"
        )
        await conexao.execute(text(sql))
    r = await c.get("/r/" + link.slug, follow_redirects=False)
    assert r.status_code == 302 and r.headers["Location"].startswith("https://wa.me/")
    assert "evento_acesso_nao_confirmado" in caplog.text and "detalhes-privados" not in caplog.text
    assert banco.motor.pool.checkedout() == 0 and await quantidade(banco) == 0
    async with banco.transacao() as s:
        assert await s.get(ModeloLink, link.id) is not None


async def test_timeout_rollback_e_fechamento_sessao(ambiente_cadastro, monkeypatch, caplog):
    c, banco, _ = ambiente_cadastro
    link, _ = await preparar_links(banco)
    c._transport.app.state.configuracao.analytics_prazo_segundos = 0.02
    original = RepositorioEventosAcessoSQLAlchemy.adicionar
    sessoes = []

    async def atrasar(self, evento):
        sessoes.append(self.sessao)
        await original(self, evento)
        await asyncio.Event().wait()

    monkeypatch.setattr(RepositorioEventosAcessoSQLAlchemy, "adicionar", atrasar)
    assert (await c.get("/r/" + link.slug, follow_redirects=False)).status_code == 302
    assert len(sessoes) == 1 and not sessoes[0].in_transaction()
    assert banco.motor.pool.checkedout() == 0 and await quantidade(banco) == 0
    assert "categoria=timeout" in caplog.text


async def test_gets_concorrentes_sessoes_proprias_sem_retries(ambiente_cadastro, monkeypatch):
    c, banco, _ = ambiente_cadastro
    link, _ = await preparar_links(banco)
    c._transport.app.state.configuracao.analytics_prazo_segundos = 2
    sessoes = []
    barreira = asyncio.Barrier(6)
    original = RepositorioEventosAcessoSQLAlchemy.adicionar

    async def sincronizar(self, evento):
        sessoes.append(self.sessao)
        await barreira.wait()
        await original(self, evento)

    monkeypatch.setattr(RepositorioEventosAcessoSQLAlchemy, "adicionar", sincronizar)
    respostas = await asyncio.gather(
        *(c.get("/r/" + link.slug, follow_redirects=False) for _ in range(6))
    )
    assert all(r.status_code == 302 for r in respostas)
    assert len(sessoes) == len({id(s) for s in sessoes}) == 6 and all(
        not s.in_transaction() for s in sessoes
    )
    assert banco.motor.pool.checkedout() == 0 and await quantidade(banco) == 6


@pytest.mark.parametrize("mudanca", ["desativar", "excluir", "remover_fisicamente"])
async def test_mudanca_concorrente_apos_leitura_valida(ambiente_cadastro, monkeypatch, mudanca):
    c, banco, _ = ambiente_cadastro
    link, _ = await preparar_links(banco)
    original = PersistenciaEventoSQLAlchemy.persistir

    async def mudar(self, evento):
        # A consulta do redirecionamento já devolveu a conexão ao pool.
        assert banco.motor.pool.checkedout() == 0
        async with banco.transacao() as s:
            if mudanca == "remover_fisicamente":
                await s.delete(await s.get(ModeloLink, link.id))
            else:
                await RepositorioLinksSQLAlchemy(s).atualizar(
                    link.excluir() if mudanca == "excluir" else replace(link, ativo=False)
                )
        await original(self, evento)

    monkeypatch.setattr(PersistenciaEventoSQLAlchemy, "persistir", mudar)
    assert (await c.get("/r/" + link.slug, follow_redirects=False)).status_code == 302
    assert await quantidade(banco) == (0 if mudanca == "remover_fisicamente" else 1)
    assert (await c.get("/r/" + link.slug, follow_redirects=False)).status_code == 404
