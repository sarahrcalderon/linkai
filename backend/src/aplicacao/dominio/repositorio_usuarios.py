from typing import Protocol
from uuid import UUID

from aplicacao.dominio.usuario import Usuario


class EmailJaCadastrado(Exception):
    """Conflito de unicidade de e-mail na persist?ncia."""


class RepositorioUsuarios(Protocol):
    async def adicionar(self, usuario: Usuario) -> None: ...

    async def obter_por_id(self, identificador: UUID) -> Usuario | None: ...

    async def obter_por_email(self, email: str) -> Usuario | None: ...
