from datetime import datetime
from typing import Protocol
from uuid import UUID

from aplicacao.dominio.evento_acesso import EventoDeAcesso


class RepositorioEventosAcesso(Protocol):
    async def adicionar(self, evento: EventoDeAcesso) -> None: ...

    async def listar_por_link(
        self,
        link_id: UUID,
        usuario_id: UUID,
        inicio: datetime,
        fim: datetime,
        limite: int = 100,
        deslocamento: int = 0,
    ) -> list[EventoDeAcesso]:
        """Intervalo [início, fim), ordem crescente por instante/UUID, com proprietário."""
        ...
