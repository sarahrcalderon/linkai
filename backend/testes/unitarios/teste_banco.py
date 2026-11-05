import pytest

from aplicacao.configuracao import Configuracao
from aplicacao.infraestrutura.banco import BancoDados, preparar_url_banco


def test_converte_url_neon_sem_expor_segredo():
    url = preparar_url_banco("postgresql://usuario:segredo@host/banco?sslmode=require")
    assert url.drivername == "postgresql+asyncpg"
    assert url.query == {"ssl": "require"}
    assert "segredo" not in str(url)
    assert "segredo" not in repr(Configuracao(url_banco=str(url)))


def test_banco_exige_configuracao_explicita():
    with pytest.raises(ValueError, match="URL_BANCO"):
        BancoDados(Configuracao(_env_file=None, url_banco=None))


def test_rejeita_outro_banco():
    with pytest.raises(ValueError):
        preparar_url_banco("sqlite:///teste.db")


@pytest.mark.parametrize("modo", ["require", "verify-ca", "verify-full", "disable"])
def test_parametros_asyncpg_neon_sem_conexao(modo):
    from sqlalchemy.ext.asyncio import create_async_engine

    url = preparar_url_banco(
        f"postgresql://usuario:ficticia@ep-exemplo.neon.tech/linkai?sslmode={modo}"
    )
    motor = create_async_engine(url, hide_parameters=True)
    _, parametros = motor.dialect.create_connect_args(motor.url)
    assert parametros["host"] == "ep-exemplo.neon.tech"
    assert parametros["ssl"] == modo
    assert "sslmode" not in parametros


def test_rejeita_modo_ssl_desconhecido():
    with pytest.raises(ValueError):
        preparar_url_banco("postgresql://usuario:ficticia@host/linkai?sslmode=invalido")
