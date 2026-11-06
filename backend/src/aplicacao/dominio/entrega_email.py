from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class EntregaReservada:
    id: UUID
    posse: UUID
    dados_cifrados: str = field(repr=False)


class RepositorioEntregas(Protocol):
    async def reservar(self) -> EntregaReservada | None: ...

    async def iniciar(self, reserva: EntregaReservada) -> bool: ...

    async def concluir(
        self, reserva: EntregaReservada, resultado: str, aguardar_segundos: float | None = None
    ) -> None: ...
