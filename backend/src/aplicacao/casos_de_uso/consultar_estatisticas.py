from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel

from aplicacao.dominio.repositorio_estatisticas import AcessosAgregados, RepositorioEstatisticas
from aplicacao.dominio.repositorio_links import LinkNaoEncontrado
from aplicacao.dominio.usuario import agora_utc


class PeriodoEstatisticasInvalido(Exception):
    """A janela deve ser uma das opções limitadas pela aplicação."""


class DiaAcessosSaida(BaseModel):
    data: date
    acessos: int


class AcessosPeriodoSaida(BaseModel):
    total_acessos: int
    data_inicial: datetime
    data_final: datetime
    serie_diaria: list[DiaAcessosSaida]


class EstatisticasLinkSaida(AcessosPeriodoSaida):
    link_id: UUID


class ResumoEstatisticasSaida(AcessosPeriodoSaida):
    links_ativos: int
    links_inativos: int


class ConsultarEstatisticas:
    def __init__(
        self, repositorio: RepositorioEstatisticas, relogio: Callable[[], datetime] | None = None
    ) -> None:
        self.repositorio = repositorio
        self.relogio = relogio or agora_utc

    def _periodo(self, dias: int) -> tuple[datetime, datetime]:
        if type(dias) is not int or dias not in {7, 30, 90}:
            raise PeriodoEstatisticasInvalido()
        agora = self.relogio()
        if agora.tzinfo is None or agora.utcoffset() is None:
            raise ValueError("Relógio de estatísticas deve incluir fuso horário.")
        fim = agora.astimezone(UTC)
        inicio = fim.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=dias - 1)
        return inicio, fim

    @staticmethod
    def _saida(agregado: AcessosAgregados, inicio: datetime, fim: datetime, dias: int) -> dict:
        return dict(
            total_acessos=agregado.total,
            data_inicial=inicio,
            data_final=fim,
            serie_diaria=[
                DiaAcessosSaida(
                    data=inicio.date() + timedelta(days=i),
                    acessos=agregado.diarios.get(inicio.date() + timedelta(days=i), 0),
                )
                for i in range(dias)
            ],
        )

    async def por_link(
        self, usuario_id: UUID, link_id: UUID, dias: int = 7
    ) -> EstatisticasLinkSaida:
        inicio, fim = self._periodo(dias)
        agregado = await self.repositorio.por_link(link_id, usuario_id, inicio, fim)
        if agregado is None:
            raise LinkNaoEncontrado()
        return EstatisticasLinkSaida(link_id=link_id, **self._saida(agregado, inicio, fim, dias))

    async def resumo(self, usuario_id: UUID, dias: int = 7) -> ResumoEstatisticasSaida:
        inicio, fim = self._periodo(dias)
        agregado = await self.repositorio.resumo(usuario_id, inicio, fim)
        return ResumoEstatisticasSaida(
            links_ativos=agregado.links_ativos,
            links_inativos=agregado.links_inativos,
            **self._saida(agregado.acessos, inicio, fim, dias),
        )
