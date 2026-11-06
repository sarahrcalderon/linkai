import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from aplicacao.dominio.link import Link
from aplicacao.dominio.repositorio_links import LinkNaoEncontrado, SlugJaUtilizado
from aplicacao.dominio.usuario import Usuario, agora_utc
from aplicacao.infraestrutura.modelos import ModeloLink, ModeloUsuario
from aplicacao.infraestrutura.repositorio_links import RepositorioLinksSQLAlchemy
from aplicacao.infraestrutura.repositorio_usuarios import RepositorioUsuariosSQLAlchemy
from testes.integracao.teste_cadastro import ambiente_cadastro as ambiente_cadastro

pytestmark = pytest.mark.postgres


async def preparar(banco):
    usuarios = [
        Usuario(nome="Pessoa", email=f"pessoa{i}@example.com", senha_hash="hash-fixture")
        for i in range(2)
    ]
    async with banco.transacao() as sessao:
        for usuario in usuarios:
            await RepositorioUsuariosSQLAlchemy(sessao).adicionar(usuario)
    return usuarios


def criar(usuario, **ajustes):
    return Link(
        **(
            dict(
                usuario_id=usuario.id,
                nome="Campanha",
                slug="campanha",
                numero_whatsapp="+5511999999999",
            )
            | ajustes
        )
    )


async def test_persistencia_propriedade_atualizacao_e_exclusao(ambiente_cadastro):
    _, banco, _ = ambiente_cadastro
    primeiro, segundo = await preparar(banco)
    link = criar(primeiro)
    async with banco.transacao() as s:
        repo = RepositorioLinksSQLAlchemy(s)
        await repo.adicionar(link)
        await repo.adicionar(criar(primeiro, slug="segunda-campanha"))
    async with banco.transacao() as s:
        repo = RepositorioLinksSQLAlchemy(s)
        assert await repo.obter_por_id(link.id, primeiro.id) == link
        assert await repo.obter_por_id(link.id, segundo.id) is None
        assert await repo.obter_publico_por_slug(" CAMPANHA ") == link
        with pytest.raises(LinkNaoEncontrado):
            await repo.atualizar(replace(link, usuario_id=segundo.id))
        with pytest.raises(ValueError):
            await repo.atualizar(replace(link, criado_em=link.criado_em - timedelta(seconds=1)))
        alterado = replace(link, nome="Novo nome", mensagem="Texto", atualizado_em=agora_utc())
        await repo.atualizar(alterado)
        assert await repo.obter_por_id(link.id, primeiro.id) == alterado
        inativo = replace(alterado, ativo=False, atualizado_em=agora_utc())
        await repo.atualizar(inativo)
        assert await repo.obter_publico_por_slug(link.slug) is None
        with pytest.raises(SlugJaUtilizado):
            await repo.adicionar(criar(segundo))
        await repo.atualizar(inativo.excluir())
    async with banco.transacao() as s:
        repo = RepositorioLinksSQLAlchemy(s)
        excluido = await repo.obter_por_id(link.id, primeiro.id)
        with pytest.raises(ValueError):
            await repo.atualizar(replace(excluido, slug="slug-alterado"))
        with pytest.raises(ValueError):
            await repo.atualizar(replace(excluido, excluido_em=None, ativo=True))
        with pytest.raises(SlugJaUtilizado):
            await repo.adicionar(criar(segundo))
        # O savepoint preserva a transação externa após conflito conhecido.
        await repo.adicionar(criar(segundo, slug="outro-slug"))


async def test_concorrencia_slug_global(ambiente_cadastro):
    _, banco, _ = ambiente_cadastro
    usuarios = await preparar(banco)
    barreira = asyncio.Barrier(2)

    async def inserir(usuario):
        try:
            async with banco.transacao() as s:
                await barreira.wait()
                await RepositorioLinksSQLAlchemy(s).adicionar(criar(usuario))
            return "persistido"
        except SlugJaUtilizado:
            return "duplicado"

    assert sorted(await asyncio.gather(*(inserir(u) for u in usuarios))) == [
        "duplicado",
        "persistido",
    ]
    async with banco.transacao() as s:
        assert await s.scalar(select(func.count()).select_from(ModeloLink)) == 1


@pytest.mark.parametrize(
    "ajustes",
    [
        {"usuario_id": uuid4()},
        {"slug": "API"},
        {"slug": "api"},
        {"slug": "slug/ruim"},
        {"numero_whatsapp": "5511999999999"},
        {"numero_whatsapp": "+012345678"},
        {"mensagem": "<b>texto</b>"},
        {"mensagem": "x" * 2001},
        {"nome": "a"},
        {"excluido_em": agora_utc()},
    ],
)
async def test_restricoes_postgresql_sem_passar_pelo_dominio(ambiente_cadastro, ajustes):
    _, banco, _ = ambiente_cadastro
    usuario, _ = await preparar(banco)
    dados = vars(criar(usuario)) | ajustes
    with pytest.raises(IntegrityError):
        async with banco.transacao() as s:
            s.add(ModeloLink(**dados))
            await s.flush()
    async with banco.transacao() as s:
        assert await s.scalar(select(func.count()).select_from(ModeloLink)) == 0


async def test_fk_restrict_e_rollback(ambiente_cadastro):
    _, banco, _ = ambiente_cadastro
    usuario, _ = await preparar(banco)
    with pytest.raises(RuntimeError):
        async with banco.transacao() as s:
            await RepositorioLinksSQLAlchemy(s).adicionar(criar(usuario))
            raise RuntimeError("Falha controlada antes do commit.")
    async with banco.transacao() as s:
        assert await s.scalar(select(func.count()).select_from(ModeloLink)) == 0
        await RepositorioLinksSQLAlchemy(s).adicionar(criar(usuario))
    with pytest.raises(IntegrityError):
        async with banco.transacao() as s:
            await s.delete(await s.get(ModeloUsuario, usuario.id))
            await s.flush()


async def test_migracao_0005_reversivel_preserva_usuarios(ambiente_cadastro):
    _, banco, esquema = ambiente_cadastro
    usuario, _ = await preparar(banco)
    async with banco.transacao() as s:
        await RepositorioLinksSQLAlchemy(s).adicionar(criar(usuario))

    def migrar(conexao, operacao, destino):
        c = Config(str(Path(__file__).parents[2] / "alembic.ini"))
        c.attributes["connection"] = conexao
        operacao(c, destino)

    async with banco.motor.begin() as conexao:
        await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
        await conexao.run_sync(migrar, command.downgrade, "0004")
        assert await conexao.scalar(text("SELECT count(*) FROM usuarios")) == 2
        assert await conexao.scalar(text("SELECT to_regclass('links')")) is None
        await conexao.run_sync(migrar, command.upgrade, "head")
        assert await conexao.scalar(text("SELECT count(*) FROM links")) == 0
