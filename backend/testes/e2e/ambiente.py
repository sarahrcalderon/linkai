"""Operações locais de homologação; nunca importado pela API pública."""

import asyncio
import json
import os
import sys
from datetime import timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import create_async_engine

from aplicacao.dominio.usuario import Usuario, agora_utc
from aplicacao.infraestrutura.banco import preparar_url_banco
from aplicacao.infraestrutura.hash_senha import HashSenhaArgon2id
from aplicacao.infraestrutura.modelos import ModeloSessao, ModeloUsuario


def obter_url():
    valor = os.environ.get("URL_BANCO_E2E", "")
    url = preparar_url_banco(valor)
    if url.host not in {"127.0.0.1", "localhost"} or url.database != "linkai_e2e":
        raise ValueError("E2E exige banco local exclusivo chamado linkai_e2e.")
    return url


async def executar(operacao: str) -> None:
    url = obter_url()
    manutencao = operacao in {"suspender", "restaurar"}
    motor = create_async_engine(
        url.set(database="postgres") if manutencao else url,
        isolation_level="AUTOCOMMIT" if manutencao else "READ COMMITTED",
        hide_parameters=True,
    )
    try:
        async with motor.begin() as conexao:
            if manutencao:
                permitir = "false" if operacao == "suspender" else "true"
                await conexao.execute(
                    text(f"ALTER DATABASE linkai_e2e ALLOW_CONNECTIONS {permitir}")
                )
                if operacao == "suspender":
                    await conexao.execute(
                        text(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                            "WHERE datname = 'linkai_e2e' AND pid <> pg_backend_pid()"
                        )
                    )
            elif operacao == "preparar":
                senha = os.environ["E2E_SENHA_FIXTURE"]

                def migrar(sincronica):
                    configuracao = Config(str(Path(__file__).parents[2] / "alembic.ini"))
                    configuracao.attributes["connection"] = sincronica
                    command.upgrade(configuracao, "head")

                await conexao.run_sync(migrar)
                await conexao.execute(
                    text(
                        "TRUNCATE links, outbox_email, limites_requisicoes, "
                        "verificacoes_email, sessoes, usuarios"
                    )
                )
                usuario = Usuario(
                    nome="Pessoa de teste",
                    email="verificado@example.com",
                    senha_hash=await HashSenhaArgon2id().gerar(senha),
                    email_verificado=True,
                )
                await conexao.execute(ModeloUsuario.__table__.insert().values(**vars(usuario)))
            elif operacao == "expirar":
                await conexao.execute(
                    update(ModeloSessao)
                    .where(
                        ModeloSessao.usuario_id.in_(
                            select(ModeloUsuario.id).where(
                                ModeloUsuario.email == "verificado@example.com"
                            )
                        )
                    )
                    .values(
                        criado_em=agora_utc() - timedelta(hours=2),
                        expira_em=agora_utc() - timedelta(hours=1),
                    )
                )
            else:
                raise ValueError("Operação de teste desconhecida.")
        print(json.dumps({"operacao": operacao, "concluida": True}))
    finally:
        await motor.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(executar(sys.argv[1]))
    except Exception:
        print("Operação E2E falhou. Verifique banco exclusivo, permissões e configuração.")
        sys.exit(1)
