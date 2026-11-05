import asyncio

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from aplicacao.configuracao import Configuracao
from aplicacao.infraestrutura.banco import preparar_url_banco
from aplicacao.infraestrutura.modelos import Base


def obter_url():
    configuracao = Configuracao()
    if configuracao.url_banco is None:
        raise ValueError("Configure URL_BANCO para executar migra??es.")
    return preparar_url_banco(configuracao.url_banco.get_secret_value())


def executar_migracoes(conexao):
    context.configure(connection=conexao, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def executar_online():
    from sqlalchemy.pool import NullPool

    motor = create_async_engine(obter_url(), poolclass=NullPool, hide_parameters=True)
    try:
        async with motor.connect() as conexao:
            await conexao.run_sync(executar_migracoes)
    finally:
        await motor.dispose()


if context.config.attributes.get("connection") is not None:
    executar_migracoes(context.config.attributes["connection"])
elif context.is_offline_mode():
    context.configure(url=obter_url(), target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(executar_online())
