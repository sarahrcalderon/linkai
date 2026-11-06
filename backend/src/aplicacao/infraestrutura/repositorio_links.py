from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aplicacao.dominio.link import Link, normalizar_slug
from aplicacao.dominio.repositorio_links import LinkNaoEncontrado, SlugJaUtilizado
from aplicacao.infraestrutura.modelos import ModeloLink


class RepositorioLinksSQLAlchemy:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def adicionar(self, link: Link) -> None:
        try:
            async with self.sessao.begin_nested():
                self.sessao.add(ModeloLink(**vars(link)))
                await self.sessao.flush()
        except IntegrityError as erro:
            causa = getattr(erro.orig, "__cause__", None)
            if getattr(causa, "constraint_name", None) == "uq_links_slug":
                raise SlugJaUtilizado("Slug já utilizado.") from None
            raise

    async def obter_por_id(self, identificador: UUID, usuario_id: UUID) -> Link | None:
        modelo = await self.sessao.scalar(
            select(ModeloLink)
            .where(ModeloLink.id == identificador, ModeloLink.usuario_id == usuario_id)
            .execution_options(populate_existing=True)
        )
        return self._converter(modelo)

    async def obter_publico_por_slug(self, slug: str) -> Link | None:
        modelo = await self.sessao.scalar(
            select(ModeloLink)
            .where(
                ModeloLink.slug == normalizar_slug(slug),
                ModeloLink.ativo.is_(True),
                ModeloLink.excluido_em.is_(None),
            )
            .execution_options(populate_existing=True)
        )
        return self._converter(modelo)

    async def obter_para_atualizacao(self, identificador: UUID, usuario_id: UUID) -> Link | None:
        modelo = await self.sessao.scalar(
            select(ModeloLink)
            .where(ModeloLink.id == identificador, ModeloLink.usuario_id == usuario_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return self._converter(modelo)

    async def listar_por_usuario(
        self, usuario_id: UUID, deslocamento: int, limite: int
    ) -> tuple[list[Link], int]:
        consulta = select(ModeloLink).where(
            ModeloLink.usuario_id == usuario_id, ModeloLink.excluido_em.is_(None)
        )
        total = await self.sessao.scalar(select(func.count()).select_from(consulta.subquery()))
        modelos = await self.sessao.scalars(
            consulta.order_by(ModeloLink.criado_em.desc(), ModeloLink.id.desc())
            .offset(deslocamento)
            .limit(limite)
            .execution_options(populate_existing=True)
        )
        return [self._converter(m) for m in modelos], total or 0

    async def atualizar(self, link: Link) -> None:
        try:
            async with self.sessao.begin_nested():
                await self._atualizar(link)
        except IntegrityError as erro:
            causa = getattr(erro.orig, "__cause__", None)
            if getattr(causa, "constraint_name", None) == "uq_links_slug":
                raise SlugJaUtilizado("Slug já utilizado.") from None
            raise

    async def _atualizar(self, link: Link) -> None:
        modelo = await self.sessao.scalar(
            select(ModeloLink)
            .where(ModeloLink.id == link.id, ModeloLink.usuario_id == link.usuario_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if modelo is None:
            raise LinkNaoEncontrado("Link não encontrado.")
        if modelo.criado_em != link.criado_em:
            raise ValueError("Data de criação não pode ser alterada.")
        if modelo.excluido_em is not None and (
            link.excluido_em != modelo.excluido_em or link.slug != modelo.slug
        ):
            raise ValueError("Exclusão lógica e reserva do slug não podem ser revertidas.")
        if link.atualizado_em < modelo.atualizado_em:
            raise ValueError("Atualização anterior ao estado persistido.")
        for campo in (
            "nome",
            "slug",
            "numero_whatsapp",
            "mensagem",
            "ativo",
            "atualizado_em",
            "excluido_em",
        ):
            setattr(modelo, campo, getattr(link, campo))
        await self.sessao.flush()

    @staticmethod
    def _converter(modelo: ModeloLink | None) -> Link | None:
        return (
            Link(**{campo: getattr(modelo, campo) for campo in Link.__dataclass_fields__})
            if modelo
            else None
        )
