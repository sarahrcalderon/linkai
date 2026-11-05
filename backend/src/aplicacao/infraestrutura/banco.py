from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aplicacao.configuracao import Configuracao


def preparar_url_banco(valor: str):
    url = make_url(valor)
    if url.drivername not in {"postgresql", "postgres", "postgresql+asyncpg"}:
        raise ValueError("Configure uma URL PostgreSQL.")
    parametros = dict(url.query)
    modo_ssl = parametros.pop("sslmode", None)
    if modo_ssl is not None:
        if modo_ssl not in {"require", "verify-ca", "verify-full", "disable"}:
            raise ValueError("Modo SSL n?o suportado.")
        parametros["ssl"] = modo_ssl
    return url.set(drivername="postgresql+asyncpg", query=parametros)


class BancoDados:
    def __init__(self, configuracao: Configuracao) -> None:
        if configuracao.url_banco is None:
            raise ValueError("Configure URL_BANCO para utilizar persist?ncia.")
        self.motor = create_async_engine(
            preparar_url_banco(configuracao.url_banco.get_secret_value()),
            echo=False,
            hide_parameters=True,
            pool_pre_ping=True,
        )
        self.sessoes = async_sessionmaker(self.motor, expire_on_commit=False)

    @asynccontextmanager
    async def transacao(self) -> AsyncIterator[AsyncSession]:
        async with self.sessoes.begin() as sessao:
            yield sessao

    async def encerrar(self) -> None:
        await self.motor.dispose()
