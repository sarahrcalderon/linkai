import asyncio
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from aplicacao.dominio.repositorio_usuarios import EmailJaCadastrado
from aplicacao.dominio.usuario import Usuario
from aplicacao.infraestrutura.banco import preparar_url_banco
from aplicacao.infraestrutura.modelos import Base, ModeloUsuario
from aplicacao.infraestrutura.repositorio_usuarios import RepositorioUsuariosSQLAlchemy


@pytest_asyncio.fixture(params=["sqlite", "postgres"])
async def sessoes(request, tmp_path):
    esquema = None
    if request.param == "postgres":
        valor = os.getenv("URL_BANCO_TESTE")
        if not valor:
            pytest.skip("URL_BANCO_TESTE n?o configurada; PostgreSQL dedicado necess?rio.")
        esquema = "teste_" + uuid4().hex
        motor = create_async_engine(preparar_url_banco(valor), hide_parameters=True)
        async with motor.begin() as conexao:
            await conexao.execute(text(f'CREATE SCHEMA "{esquema}"'))
        motor = motor.execution_options(schema_translate_map={None: esquema})
    else:
        motor = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'teste.db'}")
    try:
        async with motor.begin() as conexao:
            await conexao.run_sync(Base.metadata.create_all)
        yield async_sessionmaker(motor, expire_on_commit=False), request.param
    finally:
        if esquema:
            async with motor.begin() as conexao:
                await conexao.execute(text(f'DROP SCHEMA "{esquema}" CASCADE'))
        await motor.dispose()


def novo_usuario():
    return Usuario(nome="Ana", email="ana@exemplo.com", senha_hash="hash-de-fixture")


async def test_persiste_e_consulta(sessoes):
    fabrica, _ = sessoes
    usuario = novo_usuario()
    async with fabrica.begin() as sessao:
        await RepositorioUsuariosSQLAlchemy(sessao).adicionar(usuario)
    async with fabrica() as sessao:
        repositorio = RepositorioUsuariosSQLAlchemy(sessao)
        assert await repositorio.obter_por_id(usuario.id) == usuario
        assert await repositorio.obter_por_email(" ANA@EXEMPLO.COM ") == usuario
        assert await repositorio.obter_por_id(uuid4()) is None
        assert await repositorio.obter_por_email("ausente@exemplo.com") is None


async def test_duplicata_nao_invalida_transacao(sessoes):
    fabrica, _ = sessoes
    async with fabrica.begin() as sessao:
        repositorio = RepositorioUsuariosSQLAlchemy(sessao)
        await repositorio.adicionar(novo_usuario())
        with pytest.raises(EmailJaCadastrado):
            await repositorio.adicionar(novo_usuario())
        assert await repositorio.obter_por_email("ana@exemplo.com") is not None
        await repositorio.adicionar(
            Usuario(nome="Bia", email="bia@exemplo.com", senha_hash="hash-de-fixture")
        )
    async with fabrica() as sessao:
        assert await sessao.scalar(select(func.count()).select_from(ModeloUsuario)) == 2


async def test_rollback_transacao(sessoes):
    fabrica, _ = sessoes
    with pytest.raises(RuntimeError):
        async with fabrica.begin() as sessao:
            # Inicia uma transa??o f?sica tamb?m no driver SQLite.
            await sessao.execute(text("BEGIN") if sessoes[1] == "sqlite" else text("SELECT 1"))
            await RepositorioUsuariosSQLAlchemy(sessao).adicionar(novo_usuario())
            raise RuntimeError("Falha de opera??o composta")
    async with fabrica() as sessao:
        assert await sessao.scalar(select(func.count()).select_from(ModeloUsuario)) == 0


async def test_banco_rejeita_email_nao_normalizado(sessoes):
    fabrica, _ = sessoes
    usuario = novo_usuario()
    with pytest.raises(IntegrityError):
        async with fabrica.begin() as sessao:
            sessao.add(ModeloUsuario(**vars(usuario)))
            await sessao.flush()
            usuario.id = uuid4()
            sessao.add(ModeloUsuario(**(vars(usuario) | {"email": "ANA@EXEMPLO.COM"})))
            await sessao.flush()
    async with fabrica.begin() as sessao:
        assert await sessao.scalar(select(func.count()).select_from(ModeloUsuario)) == 0
        await RepositorioUsuariosSQLAlchemy(sessao).adicionar(novo_usuario())
    async with fabrica() as sessao:
        assert await sessao.scalar(select(func.count()).select_from(ModeloUsuario)) == 1


async def test_atualiza_usuario_e_data_utc(sessoes):
    fabrica, _ = sessoes
    usuario = novo_usuario()
    async with fabrica.begin() as sessao:
        await RepositorioUsuariosSQLAlchemy(sessao).adicionar(usuario)
    async with fabrica.begin() as sessao:
        modelo = await sessao.get(ModeloUsuario, usuario.id)
        modelo.nome = "Ana Atualizada"
        modelo.email_verificado = True
        modelo.ativo = False
    async with fabrica() as sessao:
        atualizado = await RepositorioUsuariosSQLAlchemy(sessao).obter_por_id(usuario.id)
        assert atualizado.nome == "Ana Atualizada"
        assert atualizado.email_verificado and not atualizado.ativo
        assert atualizado.atualizado_em > usuario.atualizado_em
        assert atualizado.criado_em == usuario.criado_em
        assert atualizado.atualizado_em.utcoffset().total_seconds() == 0


async def test_concorrencia_postgres(sessoes):
    fabrica, tipo = sessoes
    if tipo != "postgres":
        pytest.skip("Concorr?ncia deve ser validada no PostgreSQL.")

    async def gravar():
        try:
            async with fabrica.begin() as sessao:
                await RepositorioUsuariosSQLAlchemy(sessao).adicionar(novo_usuario())
            return "criado"
        except EmailJaCadastrado:
            return "duplicado"

    assert sorted(await asyncio.gather(gravar(), gravar())) == ["criado", "duplicado"]
    async with fabrica() as sessao:
        assert await sessao.scalar(select(func.count()).select_from(ModeloUsuario)) == 1
