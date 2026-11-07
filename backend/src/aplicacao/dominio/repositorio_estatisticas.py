from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class AcessosAgregados:
    total: int
    diarios: dict[date, int]


@dataclass(frozen=True)
class ResumoAgregado:
    links_ativos: int
    links_inativos: int
    acessos: AcessosAgregados


class RepositorioEstatisticas(Protocol):
    async def por_link(
        self, link_id: UUID, usuario_id: UUID, inicio: datetime, fim: datetime
    ) -> AcessosAgregados | None: ...

    async def resumo(self, usuario_id: UUID, inicio: datetime, fim: datetime) -> ResumoAgregado: ...
