from datetime import datetime
from typing import Protocol
from uuid import UUID

from aplicacao.dominio.verificacao_email import VerificacaoEmail


class RepositorioVerificacoes(Protocol):
    async def obter_ultima(self, usuario_id: UUID) -> VerificacaoEmail | None: ...

    async def obter_recentes(
        self, usuario_id: UUID, inicio: datetime
    ) -> list[VerificacaoEmail]: ...

    async def invalidar_anteriores(self, usuario_id: UUID, agora: datetime) -> None: ...

    async def adicionar(self, verificacao: VerificacaoEmail) -> None: ...

    async def atualizar(self, verificacao: VerificacaoEmail) -> None: ...
