from datetime import UTC, datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from aplicacao.casos_de_uso.consultar_estatisticas import (
    ConsultarEstatisticas,
    PeriodoEstatisticasInvalido,
)
from aplicacao.dominio.repositorio_estatisticas import AcessosAgregados, ResumoAgregado
from aplicacao.dominio.repositorio_links import LinkNaoEncontrado


@pytest.mark.parametrize("dias", [7, 30, 90])
async def test_periodos_e_zeros_utc(dias):
    agora = datetime(2026, 11, 6, 12, tzinfo=UTC)
    inicio = agora.replace(hour=0) - timedelta(days=dias - 1)
    repo = AsyncMock()
    repo.por_link.return_value = AcessosAgregados(2, {agora.date(): 2})
    usuario, link = uuid4(), uuid4()
    saida = await ConsultarEstatisticas(repo, lambda: agora).por_link(usuario, link, dias)
    assert saida.data_inicial == inicio and saida.data_final == agora
    assert len(saida.serie_diaria) == dias and saida.serie_diaria[-1].acessos == 2
    assert all(d.acessos == 0 for d in saida.serie_diaria[:-1])
    repo.por_link.assert_awaited_once_with(link, usuario, inicio, agora)


@pytest.mark.parametrize("dias", [0, 1, 8, 31, 91, -1, True, "7"])
async def test_periodo_invalido_sem_consulta(dias):
    repo = AsyncMock()
    with pytest.raises(PeriodoEstatisticasInvalido):
        await ConsultarEstatisticas(repo).resumo(uuid4(), dias)
    repo.resumo.assert_not_awaited()


async def test_virada_utc_e_link_ausente():
    repo = AsyncMock()
    repo.resumo.return_value = ResumoAgregado(0, 0, AcessosAgregados(0, {}))
    instante = datetime(2026, 11, 5, 21, tzinfo=timezone(timedelta(hours=-3)))
    caso = ConsultarEstatisticas(repo, lambda: instante)
    saida = await caso.resumo(uuid4(), 7)
    assert (
        saida.data_final == datetime(2026, 11, 6, tzinfo=UTC)
        and saida.serie_diaria[-1].acessos == 0
    )
    repo.por_link.return_value = None
    with pytest.raises(LinkNaoEncontrado):
        await caso.por_link(uuid4(), uuid4())
