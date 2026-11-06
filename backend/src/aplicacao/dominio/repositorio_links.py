from typing import Protocol
from uuid import UUID

from aplicacao.dominio.link import Link


class SlugJaUtilizado(Exception):
    """Slug indisponível, incluindo links excluídos ou inativos."""


class LinkNaoEncontrado(Exception):
    """Recurso ausente ou pertencente a outro usuário."""


class RepositorioLinks(Protocol):
    async def adicionar(self, link: Link) -> None: ...

    async def obter_por_id(self, identificador: UUID, usuario_id: UUID) -> Link | None: ...

    async def obter_publico_por_slug(self, slug: str) -> Link | None: ...

    async def atualizar(self, link: Link) -> None: ...

    async def obter_para_atualizacao(
        self, identificador: UUID, usuario_id: UUID
    ) -> Link | None: ...

    async def listar_por_usuario(
        self, usuario_id: UUID, deslocamento: int, limite: int
    ) -> tuple[list[Link], int]: ...
