from datetime import datetime
from typing import Protocol

from aplicacao.dominio.sessao import Sessao


class RepositorioSessoes(Protocol):
    async def adicionar(self, sessao: Sessao) -> None: ...

    async def obter_por_hash(self, token_hash: str) -> Sessao | None: ...

    async def revogar(self, token_hash: str, agora: datetime) -> None: ...
