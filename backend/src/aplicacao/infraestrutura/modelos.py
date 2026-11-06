from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    false,
    text,
    true,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from aplicacao.dominio.usuario import agora_utc


class Base(DeclarativeBase):
    pass


class ModeloUsuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        CheckConstraint("email = lower(trim(email))", name="ck_usuarios_email_normalizado"),
        CheckConstraint("length(email) BETWEEN 1 AND 254", name="ck_usuarios_email_tamanho"),
        CheckConstraint("length(trim(nome)) BETWEEN 2 AND 100", name="ck_usuarios_nome_tamanho"),
        CheckConstraint("length(senha_hash) BETWEEN 1 AND 512", name="ck_usuarios_hash_tamanho"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False, unique=True, index=True)
    senha_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    email_verificado: Mapped[bool] = mapped_column(Boolean, server_default=false(), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, server_default=true(), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, onupdate=agora_utc
    )


class ModeloSessao(Base):
    __tablename__ = "sessoes"
    __table_args__ = (
        CheckConstraint("expira_em > criado_em", name="ck_sessoes_expiracao"),
        CheckConstraint("length(token_hash) = 64", name="ck_sessoes_hash_tamanho"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModeloVerificacaoEmail(Base):
    __tablename__ = "verificacoes_email"
    __table_args__ = (
        CheckConstraint("expira_em > criado_em", name="ck_verificacoes_prazo"),
        CheckConstraint("length(codigo_hash) = 64", name="ck_verificacoes_hash"),
        CheckConstraint(
            "limite_tentativas > 0 AND tentativas >= 0 AND tentativas <= limite_tentativas",
            name="ck_verificacoes_tentativas",
        ),
        Index("ix_verificacoes_usuario_criado", "usuario_id", "criado_em"),
        Index(
            "ix_verificacoes_pendente",
            "usuario_id",
            unique=True,
            postgresql_where=text("utilizado_em IS NULL AND invalidado_em IS NULL"),
            sqlite_where=text("utilizado_em IS NULL AND invalidado_em IS NULL"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    codigo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    utilizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    limite_tentativas: Mapped[int] = mapped_column(Integer, nullable=False)
