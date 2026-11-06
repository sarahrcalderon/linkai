from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from aplicacao.dominio.repositorio_usuarios import EmailJaCadastrado
from aplicacao.dominio.usuario import Usuario
from aplicacao.infraestrutura.modelos import ModeloUsuario


class RepositorioUsuariosSQLAlchemy:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    async def adicionar(self, usuario: Usuario) -> None:
        modelo = ModeloUsuario(**vars(usuario))
        try:
            async with self.sessao.begin_nested():
                self.sessao.add(modelo)
                await self.sessao.flush()
        except IntegrityError as erro:
            # Ap?s o rollback do savepoint, distingue conflitos de e-mail de outras restri??es.
            if await self.obter_por_email(usuario.email) is not None:
                raise EmailJaCadastrado("E-mail j? cadastrado.") from None
            raise erro

    async def obter_por_id(self, identificador: UUID) -> Usuario | None:
        return self._converter(await self.sessao.get(ModeloUsuario, identificador))

    async def obter_por_email(self, email: str) -> Usuario | None:
        consulta = select(ModeloUsuario).where(ModeloUsuario.email == email.strip().lower())
        return self._converter(await self.sessao.scalar(consulta))

    async def obter_para_atualizacao(self, identificador: UUID) -> Usuario | None:
        consulta = select(ModeloUsuario).where(ModeloUsuario.id == identificador).with_for_update()
        consulta = consulta.execution_options(populate_existing=True)
        return self._converter(await self.sessao.scalar(consulta))

    async def marcar_email_verificado(self, identificador: UUID, agora: datetime) -> None:
        await self.sessao.execute(
            update(ModeloUsuario)
            .where(ModeloUsuario.id == identificador)
            .values(email_verificado=True, atualizado_em=agora)
        )

    @staticmethod
    def _converter(modelo: ModeloUsuario | None) -> Usuario | None:
        if modelo is None:
            return None
        # SQLite n?o preserva o fuso; PostgreSQL usa TIMESTAMP WITH TIME ZONE.
        return Usuario(
            id=modelo.id,
            nome=modelo.nome,
            email=modelo.email,
            senha_hash=modelo.senha_hash,
            email_verificado=modelo.email_verificado,
            ativo=modelo.ativo,
            criado_em=modelo.criado_em.replace(tzinfo=UTC)
            if modelo.criado_em.tzinfo is None
            else modelo.criado_em,
            atualizado_em=modelo.atualizado_em.replace(tzinfo=UTC)
            if modelo.atualizado_em.tzinfo is None
            else modelo.atualizado_em,
        )
