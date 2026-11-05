from io import StringIO
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_migracao_postgres_offline(monkeypatch):
    monkeypatch.setenv("URL_BANCO", "postgresql://usuario:senha@localhost/teste")
    saida = StringIO()
    configuracao = Config(str(Path(__file__).parents[2] / "alembic.ini"), output_buffer=saida)
    command.upgrade(configuracao, "head", sql=True)
    sql = saida.getvalue()
    assert "CREATE TABLE usuarios" in sql
    assert "CREATE UNIQUE INDEX ix_usuarios_email" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "senha" not in sql.replace("senha_hash", "")
    saida.seek(0)
    saida.truncate()
    command.downgrade(configuracao, "0002:base", sql=True)
    assert "DROP TABLE usuarios" in saida.getvalue()
    assert "DROP TABLE sessoes" in saida.getvalue()


def test_aplica_reverte_e_compara_modelos(tmp_path):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from sqlalchemy import create_engine, inspect

    from aplicacao.infraestrutura.modelos import Base

    motor = create_engine(f"sqlite:///{tmp_path / 'migracao.db'}")
    try:
        with motor.begin() as conexao:
            configuracao = Config(str(Path(__file__).parents[2] / "alembic.ini"))
            configuracao.attributes["connection"] = conexao
            command.upgrade(configuracao, "head")
            assert "usuarios" in inspect(conexao).get_table_names()
            assert compare_metadata(MigrationContext.configure(conexao), Base.metadata) == []
            command.downgrade(configuracao, "base")
            assert "usuarios" not in inspect(conexao).get_table_names()
    finally:
        motor.dispose()
