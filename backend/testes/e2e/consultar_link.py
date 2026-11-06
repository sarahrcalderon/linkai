"""Asserções locais somente leitura, sem imprimir valores de registros."""

import asyncio
import json
import sys
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from aplicacao.infraestrutura.modelos import ModeloLink
from testes.e2e.ambiente import obter_url


async def consultar(entrada: dict) -> dict:
    motor = create_async_engine(obter_url(), hide_parameters=True)
    try:
        async with motor.begin() as conexao:
            await conexao.execute(text("SET TRANSACTION READ ONLY"))
            if entrada.get("operacao") == "metadados":
                return {
                    "postgresql": await conexao.scalar(text("SHOW server_version")),
                    "revisao": await conexao.scalar(
                        text("SELECT version_num FROM alembic_version")
                    ),
                }
            registro = (
                (
                    await conexao.execute(
                        select(ModeloLink).where(ModeloLink.id == UUID(entrada["id"]))
                    )
                )
                .mappings()
                .one_or_none()
            )
            if registro is None:
                return {"encontrado": False}
            esperado = entrada.get("esperado", {})
            permitidos = {"nome", "slug", "numero_whatsapp", "mensagem", "ativo"}
            return {
                "encontrado": True,
                "campos_correspondem": all(
                    c in permitidos and registro[c] == v
                    for c, v in esperado.items()
                    if c != "excluido"
                ),
                "exclusao_corresponde": "excluido" not in esperado
                or (registro["excluido_em"] is not None) == esperado["excluido"],
            }
    finally:
        await motor.dispose()


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(consultar(json.load(sys.stdin)))))
    except Exception:
        raise SystemExit("Consulta de teste indisponível; detalhes omitidos.") from None
