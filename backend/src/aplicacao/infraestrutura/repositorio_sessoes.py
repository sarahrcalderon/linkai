from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aplicacao.dominio.sessao import Sessao
from aplicacao.infraestrutura.modelos import ModeloSessao


def converter_utc(data: datetime) -> datetime:
    return data.astimezone(UTC) if data.tzinfo else data.replace(tzinfo=UTC)


class RepositorioSessoesSQLAlchemy:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def adicionar(self, sessao: Sessao) -> None:
        self.sessao.add(ModeloSessao(**vars(sessao)))
        await self.sessao.flush()

    async def obter_por_hash(self, token_hash: str) -> Sessao | None:
        modelo = await self.sessao.scalar(
            select(ModeloSessao).where(ModeloSessao.token_hash == token_hash)
        )
        if modelo is None:
            return None
        return Sessao(
            id=modelo.id,
            usuario_id=modelo.usuario_id,
            token_hash=modelo.token_hash,
            criado_em=converter_utc(modelo.criado_em),
            expira_em=converter_utc(modelo.expira_em),
            revogado_em=converter_utc(modelo.revogado_em) if modelo.revogado_em else None,
        )

    async def revogar(self, token_hash: str, agora: datetime) -> None:
        # Operação atômica e idempotente, inclusive em logouts concorrentes.
        await self.sessao.execute(
            update(ModeloSessao)
            .where(ModeloSessao.token_hash == token_hash, ModeloSessao.revogado_em.is_(None))
            .values(revogado_em=agora)
        )
