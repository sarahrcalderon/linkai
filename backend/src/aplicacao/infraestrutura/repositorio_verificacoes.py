from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aplicacao.dominio.verificacao_email import VerificacaoEmail
from aplicacao.infraestrutura.modelos import ModeloVerificacaoEmail
from aplicacao.infraestrutura.repositorio_sessoes import converter_utc


class RepositorioVerificacoesSQLAlchemy:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def obter_ultima(self, usuario_id: UUID) -> VerificacaoEmail | None:
        modelo = await self.sessao.scalar(
            select(ModeloVerificacaoEmail)
            .where(ModeloVerificacaoEmail.usuario_id == usuario_id)
            .order_by(ModeloVerificacaoEmail.criado_em.desc(), ModeloVerificacaoEmail.id.desc())
            .limit(1)
        )
        if modelo is None:
            return None
        return self._converter(modelo)

    @staticmethod
    def _converter(modelo: ModeloVerificacaoEmail) -> VerificacaoEmail:
        return VerificacaoEmail(
            id=modelo.id,
            usuario_id=modelo.usuario_id,
            codigo_hash=modelo.codigo_hash,
            criado_em=converter_utc(modelo.criado_em),
            expira_em=converter_utc(modelo.expira_em),
            utilizado_em=converter_utc(modelo.utilizado_em) if modelo.utilizado_em else None,
            invalidado_em=converter_utc(modelo.invalidado_em) if modelo.invalidado_em else None,
            tentativas=modelo.tentativas,
            limite_tentativas=modelo.limite_tentativas,
        )

    async def obter_recentes(self, usuario_id: UUID, inicio: datetime) -> list[VerificacaoEmail]:
        modelos = await self.sessao.scalars(
            select(ModeloVerificacaoEmail).where(
                ModeloVerificacaoEmail.usuario_id == usuario_id,
                ModeloVerificacaoEmail.criado_em >= inicio,
            )
        )
        return [self._converter(modelo) for modelo in modelos]

    async def invalidar_anteriores(self, usuario_id: UUID, agora: datetime) -> None:
        await self.sessao.execute(
            update(ModeloVerificacaoEmail)
            .where(
                ModeloVerificacaoEmail.usuario_id == usuario_id,
                ModeloVerificacaoEmail.utilizado_em.is_(None),
                ModeloVerificacaoEmail.invalidado_em.is_(None),
            )
            .values(invalidado_em=agora)
        )

    async def adicionar(self, verificacao: VerificacaoEmail) -> None:
        self.sessao.add(ModeloVerificacaoEmail(**vars(verificacao)))
        await self.sessao.flush()

    async def atualizar(self, verificacao: VerificacaoEmail) -> None:
        await self.sessao.execute(
            update(ModeloVerificacaoEmail)
            .where(ModeloVerificacaoEmail.id == verificacao.id)
            .values(
                tentativas=verificacao.tentativas,
                utilizado_em=verificacao.utilizado_em,
                invalidado_em=verificacao.invalidado_em,
            )
        )
