from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aplicacao.dominio.evento_acesso import EventoDeAcesso
from aplicacao.infraestrutura.modelos import ModeloEventoAcesso, ModeloLink


class RepositorioEventosAcessoSQLAlchemy:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def adicionar(self, evento: EventoDeAcesso) -> None:
        self.sessao.add(
            ModeloEventoAcesso(
                id=evento.id,
                link_id=evento.link_id,
                acessado_em=evento.acessado_em,
            )
        )
        await self.sessao.flush()

    async def listar_por_link(
        self,
        link_id: UUID,
        usuario_id: UUID,
        inicio: datetime,
        fim: datetime,
        limite: int = 100,
        deslocamento: int = 0,
    ) -> list[EventoDeAcesso]:
        for data in (inicio, fim):
            if not isinstance(data, datetime) or data.tzinfo is None or data.utcoffset() is None:
                raise ValueError("Período deve conter datas com fuso horário.")
        if inicio >= fim:
            raise ValueError("Fim do período deve ser posterior ao início.")
        if type(limite) is not int or not 1 <= limite <= 1000:
            raise ValueError("Limite deve estar entre 1 e 1000.")
        if type(deslocamento) is not int or not 0 <= deslocamento <= 1000000:
            raise ValueError("Deslocamento deve estar entre 0 e 1000000.")
        consulta = (
            select(ModeloEventoAcesso)
            .join(ModeloLink, ModeloLink.id == ModeloEventoAcesso.link_id)
            .where(
                ModeloEventoAcesso.link_id == link_id,
                ModeloLink.usuario_id == usuario_id,
                ModeloEventoAcesso.acessado_em >= inicio.astimezone(UTC),
                ModeloEventoAcesso.acessado_em < fim.astimezone(UTC),
            )
            .order_by(ModeloEventoAcesso.acessado_em, ModeloEventoAcesso.id)
            .limit(limite)
            .offset(deslocamento)
        )
        modelos = await self.sessao.scalars(consulta)
        return [
            EventoDeAcesso(id=m.id, link_id=m.link_id, acessado_em=m.acessado_em) for m in modelos
        ]
