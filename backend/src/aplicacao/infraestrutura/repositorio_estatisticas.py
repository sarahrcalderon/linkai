from datetime import datetime
from uuid import UUID

from sqlalchemy import Date, and_, cast, func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from aplicacao.dominio.repositorio_estatisticas import AcessosAgregados, ResumoAgregado
from aplicacao.infraestrutura.modelos import ModeloEventoAcesso as Evento
from aplicacao.infraestrutura.modelos import ModeloLink as Link


class RepositorioEstatisticasSQLAlchemy:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    @staticmethod
    def _dia():
        return cast(func.timezone("UTC", Evento.acessado_em), Date)

    @staticmethod
    def _acessos(linhas) -> AcessosAgregados:
        return AcessosAgregados(
            total=int(linhas[0].total),
            diarios={r.dia: int(r.acessos) for r in linhas if r.dia is not None},
        )

    async def por_link(
        self, link_id: UUID, usuario_id: UUID, inicio: datetime, fim: datetime
    ) -> AcessosAgregados | None:
        dia = self._dia()
        consulta = (
            select(
                dia.label("dia"),
                func.count(Evento.id).label("acessos"),
                func.sum(func.count(Evento.id)).over().label("total"),
            )
            .select_from(Link)
            .outerjoin(
                Evento,
                and_(
                    Evento.link_id == Link.id,
                    Evento.acessado_em >= inicio,
                    Evento.acessado_em < fim,
                ),
            )
            .where(Link.id == link_id, Link.usuario_id == usuario_id, Link.excluido_em.is_(None))
            .group_by(dia)
            .order_by(dia)
        )
        linhas = (await self.sessao.execute(consulta)).all()
        return self._acessos(linhas) if linhas else None

    async def resumo(self, usuario_id: UUID, inicio: datetime, fim: datetime) -> ResumoAgregado:
        dono = (Link.usuario_id == usuario_id, Link.excluido_em.is_(None))
        contagens = (
            select(
                func.count().filter(Link.ativo.is_(True)).label("links_ativos"),
                func.count().filter(Link.ativo.is_(False)).label("links_inativos"),
            )
            .select_from(Link)
            .where(*dono)
            .subquery()
        )
        dia = self._dia()
        serie = (
            select(
                dia.label("dia"),
                func.count(Evento.id).label("acessos"),
                func.sum(func.count(Evento.id)).over().label("total"),
            )
            .select_from(Evento)
            .join(Link, Link.id == Evento.link_id)
            .where(*dono, Evento.acessado_em >= inicio, Evento.acessado_em < fim)
            .group_by(dia)
        ).subquery()
        consulta = (
            select(
                contagens.c.links_ativos,
                contagens.c.links_inativos,
                serie.c.dia,
                func.coalesce(serie.c.acessos, 0).label("acessos"),
                func.coalesce(serie.c.total, 0).label("total"),
            )
            .select_from(contagens.outerjoin(serie, true()))
            .order_by(serie.c.dia)
        )
        linhas = (await self.sessao.execute(consulta)).all()
        return ResumoAgregado(
            links_ativos=int(linhas[0].links_ativos),
            links_inativos=int(linhas[0].links_inativos),
            acessos=self._acessos(linhas),
        )
