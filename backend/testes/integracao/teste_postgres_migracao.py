import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from aplicacao.infraestrutura.banco import preparar_url_banco
from aplicacao.infraestrutura.modelos import Base


@pytest.mark.postgres
async def test_upgrade_downgrade_upgrade_postgres():
    valor = os.getenv("URL_BANCO_TESTE")
    if not valor:
        pytest.skip("Configure URL_BANCO_TESTE para homologar PostgreSQL.")
    esquema = "teste_migracao_" + uuid4().hex
    motor = create_async_engine(preparar_url_banco(valor), hide_parameters=True)

    def migrar(conexao, operacao, destino):
        configuracao = Config(str(Path(__file__).parents[2] / "alembic.ini"))
        configuracao.attributes["connection"] = conexao
        operacao(configuracao, destino)

    def verificar_modelos(conexao):
        assert "usuarios" in inspect(conexao).get_table_names()
        assert compare_metadata(MigrationContext.configure(conexao), Base.metadata) == []

    try:
        async with motor.begin() as conexao:
            await conexao.execute(text(f'CREATE SCHEMA "{esquema}"'))
        async with motor.begin() as conexao:
            await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
            await conexao.run_sync(migrar, command.upgrade, "head")
            await conexao.run_sync(verificar_modelos)
            assert await conexao.scalar(text("SELECT version_num FROM alembic_version")) == "0002"
        # A reversão exclusiva da 3.3 deve preservar usuários da 3.2.
        async with motor.begin() as conexao:
            await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
            await conexao.execute(
                text(
                    "INSERT INTO usuarios (id, nome, email, senha_hash, criado_em, atualizado_em) "
                    "VALUES (:id, 'Ana', 'ana@example.com', 'hash-fixture', now(), now())"
                ),
                {"id": uuid4()},
            )
            await conexao.run_sync(migrar, command.downgrade, "0001")
            assert await conexao.scalar(text("SELECT count(*) FROM usuarios")) == 1
            tabelas = await conexao.run_sync(
                lambda sincronica: inspect(sincronica).get_table_names()
            )
            assert "sessoes" not in tabelas
        async with motor.begin() as conexao:
            await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
            await conexao.run_sync(migrar, command.upgrade, "head")
            assert await conexao.scalar(text("SELECT count(*) FROM usuarios")) == 1
            await conexao.run_sync(verificar_modelos)
        async with motor.begin() as conexao:
            await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
            await conexao.run_sync(migrar, command.downgrade, "base")
            tabelas = await conexao.run_sync(
                lambda sincronica: inspect(sincronica).get_table_names()
            )
            assert "usuarios" not in tabelas
        async with motor.begin() as conexao:
            await conexao.execute(text(f'SET LOCAL search_path TO "{esquema}"'))
            await conexao.run_sync(migrar, command.upgrade, "head")
            await conexao.run_sync(verificar_modelos)
    finally:
        async with motor.begin() as conexao:
            await conexao.execute(text(f'DROP SCHEMA IF EXISTS "{esquema}" CASCADE'))
        await motor.dispose()
