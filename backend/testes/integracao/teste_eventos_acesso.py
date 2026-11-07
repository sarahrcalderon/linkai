import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from aplicacao.dominio.evento_acesso import EventoDeAcesso
from aplicacao.infraestrutura.modelos import ModeloEventoAcesso, ModeloLink
from aplicacao.infraestrutura.repositorio_eventos_acesso import RepositorioEventosAcessoSQLAlchemy
from aplicacao.infraestrutura.repositorio_links import RepositorioLinksSQLAlchemy
from testes.integracao.teste_cadastro import ambiente_cadastro as ambiente_cadastro
from testes.integracao.teste_links import criar, preparar

pytestmark = pytest.mark.postgres


async def preparar_links(banco):
    primeiro, segundo = await preparar(banco)
    links = [criar(primeiro, slug="link-primeiro"), criar(segundo, slug="link-segundo")]
    async with banco.transacao() as s:
        for link in links:
            await RepositorioLinksSQLAlchemy(s).adicionar(link)
    return links


async def test_persistencia_periodo_ordenacao_e_proprietario_sem_n_mais_um(ambiente_cadastro):
    _, banco, _ = ambiente_cadastro
    primeiro, segundo = await preparar_links(banco)
    inicio = datetime(2026, 1, 1, tzinfo=UTC)
    eventos = [
        EventoDeAcesso(link_id=primeiro.id, acessado_em=inicio + timedelta(hours=h))
        for h in [2, 1, 1, 0, 3]
    ]
    async with banco.transacao() as s:
        repo = RepositorioEventosAcessoSQLAlchemy(s)
        for e in eventos:
            await repo.adicionar(e)
        await repo.adicionar(EventoDeAcesso(link_id=segundo.id, acessado_em=inicio))
    consultas = []

    def contar(*args):
        consultas.append(True)

    async with banco.transacao() as s:
        repo = RepositorioEventosAcessoSQLAlchemy(s)
        event.listen(banco.motor.sync_engine, "before_cursor_execute", contar)
        try:
            obtidos = await repo.listar_por_link(
                primeiro.id, primeiro.usuario_id, inicio, inicio + timedelta(hours=3)
            )
        finally:
            event.remove(banco.motor.sync_engine, "before_cursor_execute", contar)
        esperados = sorted(eventos[:4], key=lambda e: (e.acessado_em, e.id))
        assert obtidos == esperados and len(consultas) == 1
        assert all(e.acessado_em.tzinfo is UTC for e in obtidos)
        assert (
            await repo.listar_por_link(
                primeiro.id, segundo.usuario_id, inicio, inicio + timedelta(days=1)
            )
            == []
        )
        assert (
            await repo.listar_por_link(
                uuid4(), primeiro.usuario_id, inicio, inicio + timedelta(days=1)
            )
            == []
        )
        assert (
            await repo.listar_por_link(
                primeiro.id,
                primeiro.usuario_id,
                inicio,
                inicio + timedelta(hours=3),
                limite=2,
                deslocamento=1,
            )
            == esperados[1:3]
        )
    assert set(ModeloEventoAcesso.__table__.columns.keys()) == {"id", "link_id", "acessado_em"}


async def test_fk_inexistente_e_rollback(ambiente_cadastro):
    _, banco, _ = ambiente_cadastro
    with pytest.raises(IntegrityError):
        async with banco.transacao() as s:
            await RepositorioEventosAcessoSQLAlchemy(s).adicionar(EventoDeAcesso(link_id=uuid4()))
    link, _ = await preparar_links(banco)
    with pytest.raises(RuntimeError):
        async with banco.transacao() as s:
            await RepositorioEventosAcessoSQLAlchemy(s).adicionar(EventoDeAcesso(link_id=link.id))
            raise RuntimeError("Falha controlada antes do commit.")
    async with banco.transacao() as s:
        assert await s.scalar(select(func.count()).select_from(ModeloEventoAcesso)) == 0


async def test_concorrencia_preserva_todas_tentativas_e_uuid_unico(ambiente_cadastro):
    _, banco, _ = ambiente_cadastro
    link, _ = await preparar_links(banco)
    instante = datetime(2026, 1, 1, tzinfo=UTC)
    barreira = asyncio.Barrier(8)

    async def inserir():
        async with banco.transacao() as s:
            await barreira.wait()
            await RepositorioEventosAcessoSQLAlchemy(s).adicionar(
                EventoDeAcesso(link_id=link.id, acessado_em=instante)
            )

    await asyncio.gather(*(inserir() for _ in range(8)))
    evento = EventoDeAcesso(link_id=link.id, acessado_em=instante)
    async with banco.transacao() as s:
        await RepositorioEventosAcessoSQLAlchemy(s).adicionar(evento)
    with pytest.raises(IntegrityError):
        async with banco.transacao() as s:
            await RepositorioEventosAcessoSQLAlchemy(s).adicionar(evento)
    async with banco.transacao() as s:
        assert await s.scalar(select(func.count()).select_from(ModeloEventoAcesso)) == 9


async def test_exclusao_logica_preserva_historico_e_fisica_cascateia(ambiente_cadastro):
    _, banco, _ = ambiente_cadastro
    link, _ = await preparar_links(banco)
    evento = EventoDeAcesso(link_id=link.id)
    async with banco.transacao() as s:
        await RepositorioEventosAcessoSQLAlchemy(s).adicionar(evento)
        await RepositorioLinksSQLAlchemy(s).atualizar(link.excluir())
    async with banco.transacao() as s:
        resultado = await RepositorioEventosAcessoSQLAlchemy(s).listar_por_link(
            link.id,
            link.usuario_id,
            evento.acessado_em - timedelta(seconds=1),
            evento.acessado_em + timedelta(seconds=1),
        )
        assert resultado == [evento]
        # Operação administrativa apenas de fixture; não existe DELETE físico na API.
        await s.delete(await s.get(ModeloLink, link.id))
    async with banco.transacao() as s:
        assert await s.scalar(select(func.count()).select_from(ModeloEventoAcesso)) == 0


@pytest.mark.parametrize(
    "ajustes",
    [
        {"limite": 0},
        {"limite": 1001},
        {"limite": True},
        {"deslocamento": -1},
        {"deslocamento": 1000001},
        {"inicio": datetime(2026, 1, 1)},
        {"fim": datetime(2025, 1, 1, tzinfo=UTC)},
    ],
)
async def test_consulta_invalida(ambiente_cadastro, ajustes):
    _, banco, _ = ambiente_cadastro
    parametros = (
        dict(
            link_id=uuid4(),
            usuario_id=uuid4(),
            inicio=datetime(2026, 1, 1, tzinfo=UTC),
            fim=datetime(2026, 1, 2, tzinfo=UTC),
        )
        | ajustes
    )
    async with banco.transacao() as s:
        with pytest.raises(ValueError):
            await RepositorioEventosAcessoSQLAlchemy(s).listar_por_link(**parametros)


async def test_redirecionamento_captura_somente_acesso_valido(ambiente_cadastro):
    c, banco, _ = ambiente_cadastro
    link, _ = await preparar_links(banco)
    assert (await c.get("/r/" + link.slug, follow_redirects=False)).status_code == 302
    assert (await c.get("/r/inexistente", follow_redirects=False)).status_code == 404
    async with banco.transacao() as s:
        assert await s.scalar(select(func.count()).select_from(ModeloEventoAcesso)) == 1


async def test_migracao_0006_reversivel_preserva_link(ambiente_cadastro):
    _, banco, esquema = ambiente_cadastro
    link, _ = await preparar_links(banco)
    async with banco.transacao() as s:
        await RepositorioEventosAcessoSQLAlchemy(s).adicionar(EventoDeAcesso(link_id=link.id))

    def migrar(conexao, operacao, destino):
        cfg = Config(str(Path(__file__).parents[2] / "alembic.ini"))
        cfg.attributes["connection"] = conexao
        operacao(cfg, destino)

    async with banco.motor.begin() as conexao:
        await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
        await conexao.run_sync(migrar, command.downgrade, "0005")
        assert await conexao.scalar(text("SELECT to_regclass('eventos_acesso')")) is None
        assert await conexao.scalar(text("SELECT count(*) FROM links")) == 2
        await conexao.run_sync(migrar, command.upgrade, "head")
        assert await conexao.scalar(text("SELECT count(*) FROM eventos_acesso")) == 0
