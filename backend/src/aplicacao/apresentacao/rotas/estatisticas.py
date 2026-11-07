from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict

from aplicacao.apresentacao.dependencias_autenticacao import TransacaoHTTP
from aplicacao.apresentacao.rotas.links import Proprietario
from aplicacao.casos_de_uso.consultar_estatisticas import (
    ConsultarEstatisticas,
    EstatisticasLinkSaida,
    ResumoEstatisticasSaida,
)
from aplicacao.infraestrutura.repositorio_estatisticas import RepositorioEstatisticasSQLAlchemy

roteador_estatisticas = APIRouter(tags=["Estatísticas"])


class PeriodoEntradaHTTP(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dias: Literal["7", "30", "90"] = "7"


def obter_estatisticas(transacao: TransacaoHTTP) -> ConsultarEstatisticas:
    return ConsultarEstatisticas(RepositorioEstatisticasSQLAlchemy(transacao))


Caso = Annotated[ConsultarEstatisticas, Depends(obter_estatisticas)]
Periodo = Annotated[PeriodoEntradaHTTP, Query()]


@roteador_estatisticas.get(
    "/links/{identificador}/estatisticas", response_model=EstatisticasLinkSaida
)
async def estatisticas_link(
    identificador: UUID, usuario: Proprietario, periodo: Periodo, caso: Caso, resposta: Response
):
    resposta.headers["Cache-Control"] = "private, no-store"
    return await caso.por_link(usuario, identificador, int(periodo.dias))


@roteador_estatisticas.get("/estatisticas/resumo", response_model=ResumoEstatisticasSaida)
async def resumo_estatisticas(
    usuario: Proprietario, periodo: Periodo, caso: Caso, resposta: Response
):
    resposta.headers["Cache-Control"] = "private, no-store"
    return await caso.resumo(usuario, int(periodo.dias))
