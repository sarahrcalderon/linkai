"""Operações controladas somente no banco local linkai_e2e; fora da API pública."""

import asyncio
import json
import sys
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

from aplicacao.dominio.link import Link
from aplicacao.infraestrutura.modelos import ModeloEventoAcesso, ModeloLink, ModeloUsuario
from testes.e2e.ambiente import obter_url


async def executar(entrada: dict) -> dict:
    motor = create_async_engine(obter_url(), hide_parameters=True)
    try:
        async with motor.begin() as c:
            operacao = entrada["operacao"]
            if operacao == "consultar":
                await c.execute(text("SET TRANSACTION READ ONLY"))
                parametros = {
                    "email": entrada.get("email", "verificado@example.com"),
                    "inicio": datetime.fromisoformat(entrada["inicio"]),
                    "fim": datetime.fromisoformat(entrada["fim"]),
                    "id": UUID(entrada["id"]) if entrada.get("id") else None,
                }
                # Consulta SQL independente do repositório usado pela API.
                filtro = " AND l.id = :id" if parametros["id"] else ""
                linhas = (
                    await c.execute(
                        text(
                            "SELECT (e.acessado_em AT TIME ZONE 'UTC')::date AS dia, "
                            "count(*) AS total FROM eventos_acesso e "
                            "JOIN links l ON l.id=e.link_id JOIN usuarios u ON u.id=l.usuario_id "
                            "WHERE u.email=:email AND l.excluido_em IS NULL "
                            "AND e.acessado_em>=:inicio AND e.acessado_em<:fim"
                            + filtro
                            + " GROUP BY dia ORDER BY dia"
                        ),
                        parametros,
                    )
                ).all()
                estados = (
                    await c.execute(
                        text(
                            "SELECT count(*) FILTER (WHERE l.ativo), "
                            "count(*) FILTER (WHERE NOT l.ativo) FROM links l "
                            "JOIN usuarios u ON u.id=l.usuario_id "
                            "WHERE u.email=:email AND l.excluido_em IS NULL"
                        ),
                        parametros,
                    )
                ).one()
                return {
                    "total": sum(linha.total for linha in linhas),
                    "diarios": {str(linha.dia): linha.total for linha in linhas},
                    "ativos": estados[0],
                    "inativos": estados[1],
                }
            if operacao == "contar":
                await c.execute(text("SET TRANSACTION READ ONLY"))
                id_link = UUID(entrada["id"])
                return {
                    "link_persistido": bool(
                        await c.scalar(select(ModeloLink.id).where(ModeloLink.id == id_link))
                    ),
                    "eventos": await c.scalar(
                        text("SELECT count(*) FROM eventos_acesso WHERE link_id=:id"),
                        {"id": id_link},
                    ),
                }
            if operacao in {"falhar", "restaurar"}:
                await c.execute(
                    text("DROP TRIGGER IF EXISTS falha_analytics_e2e ON eventos_acesso")
                )
                await c.execute(text("DROP FUNCTION IF EXISTS falha_analytics_e2e()"))
                if operacao == "falhar":
                    id_link = UUID(entrada["id"])
                    # UUID validado; nenhum texto fornecido pelo cliente entra no DDL.
                    await c.execute(
                        text(
                            "CREATE FUNCTION falha_analytics_e2e() RETURNS trigger "
                            "LANGUAGE plpgsql AS $$ BEGIN IF NEW.link_id = '"
                            + str(id_link)
                            + "'::uuid THEN RAISE EXCEPTION 'falha controlada' "
                            "USING ERRCODE='23514'; END IF; RETURN NEW; END $$"
                        )
                    )
                    await c.execute(
                        text(
                            "CREATE TRIGGER falha_analytics_e2e BEFORE INSERT ON eventos_acesso "
                            "FOR EACH ROW EXECUTE FUNCTION falha_analytics_e2e()"
                        )
                    )
                return {"concluido": True}
            if operacao == "semear":
                usuarios = dict(
                    (await c.execute(select(ModeloUsuario.email, ModeloUsuario.id))).all()
                )
                ids = {}
                for slug, email, ativo, excluido in [
                    ("historico", "verificado@example.com", True, False),
                    ("historico-inativo", "verificado@example.com", False, False),
                    ("historico-excluido", "verificado@example.com", True, True),
                    ("sem-acessos", "verificado@example.com", True, False),
                    ("outro-historico", "outro@example.com", True, False),
                ]:
                    link = Link(
                        usuario_id=usuarios[email],
                        nome=slug,
                        slug=slug,
                        numero_whatsapp="+5511999999999",
                        ativo=ativo,
                    )
                    if excluido:
                        link = link.excluir()
                    await c.execute(ModeloLink.__table__.insert().values(**vars(link)))
                    ids[slug] = str(link.id)
                    if slug != "sem-acessos":
                        instantes = (
                            (
                                await c.execute(
                                    text(
                                        "SELECT instante FROM (VALUES "
                                        "(date_trunc('day', now() AT TIME ZONE 'UTC') "
                                        "AT TIME ZONE 'UTC' - interval '100 days'),"
                                        "(date_trunc('day', now() AT TIME ZONE 'UTC') "
                                        "AT TIME ZONE 'UTC' - interval '29 days'),"
                                        "(date_trunc('day', now() AT TIME ZONE 'UTC') "
                                        "AT TIME ZONE 'UTC' - interval '6 days 1 microsecond'),"
                                        "(date_trunc('day', now() AT TIME ZONE 'UTC') "
                                        "AT TIME ZONE 'UTC' - interval '6 days'),"
                                        "(date_trunc('day', now() AT TIME ZONE 'UTC') "
                                        "AT TIME ZONE 'UTC' - interval '1 microsecond'),"
                                        "(date_trunc('day', now() AT TIME ZONE 'UTC') "
                                        "AT TIME ZONE 'UTC'),"
                                        "(now() + interval '2 days')) AS datas(instante)"
                                    )
                                )
                            )
                            .scalars()
                            .all()
                        )
                        await c.execute(
                            ModeloEventoAcesso.__table__.insert(),
                            [dict(id=uuid4(), link_id=link.id, acessado_em=d) for d in instantes],
                        )
                return ids
            raise ValueError("Operação desconhecida.")
    finally:
        await motor.dispose()


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(executar(json.load(sys.stdin)))))
    except Exception:
        raise SystemExit("Operação Analytics E2E falhou; detalhes omitidos.") from None
