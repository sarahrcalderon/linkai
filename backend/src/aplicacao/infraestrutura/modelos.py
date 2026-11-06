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
    Text,
    UniqueConstraint,
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


class ModeloLink(Base):
    __tablename__ = "links"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_links_slug"),
        CheckConstraint(
            "length(nome) BETWEEN 2 AND 100 AND nome = trim(nome)", name="ck_links_nome"
        ),
        CheckConstraint(
            "length(slug) BETWEEN 3 AND 64 AND slug = lower(trim(slug))", name="ck_links_slug"
        ),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_links_slug_formato").ddl_if(
            dialect="postgresql"
        ),
        CheckConstraint("numero_whatsapp ~ '^\\+[1-9][0-9]{7,14}$'", name="ck_links_numero").ddl_if(
            dialect="postgresql"
        ),
        CheckConstraint(
            "slug NOT IN ('api','admin','login','logout','cadastro','dashboard',"
            "'verificar-email','reenviar-codigo','static','assets','docs',"
            "'redoc','openapi','saude','www')",
            name="ck_links_slug_reservado",
        ),
        CheckConstraint(
            "mensagem IS NULL OR (length(mensagem) <= 2000 "
            "AND mensagem NOT LIKE '%<%' AND mensagem NOT LIKE '%>%')",
            name="ck_links_mensagem",
        ),
        CheckConstraint("atualizado_em >= criado_em", name="ck_links_datas"),
        CheckConstraint(
            "excluido_em IS NULL OR (ativo = false AND excluido_em >= criado_em "
            "AND excluido_em <= atualizado_em)",
            name="ck_links_exclusao",
        ),
        Index("ix_links_usuario_criado", "usuario_id", "criado_em"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    usuario_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_whatsapp: Mapped[str] = mapped_column(String(16), nullable=False)
    mensagem: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    excluido_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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


class ModeloEntregaEmail(Base):
    __tablename__ = "outbox_email"
    __table_args__ = (
        CheckConstraint("tentativas >= 0", name="ck_outbox_tentativas"),
        CheckConstraint(
            "estado IN ('pendente','processando','enviada','falha','indeterminada','cancelada')",
            name="ck_outbox_estado",
        ),
        Index("ix_outbox_prontas", "estado", "proxima_tentativa"),
    )
    id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("verificacoes_email.id", ondelete="CASCADE"), primary_key=True
    )
    dados_cifrados: Mapped[str | None] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(20), nullable=False, server_default="pendente")
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    proxima_tentativa: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrendado_ate: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    posse: Mapped[UUID | None] = mapped_column(Uuid)
    envio_iniciado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ultima_falha: Mapped[str | None] = mapped_column(String(40))


class ModeloLimiteRequisicoes(Base):
    __tablename__ = "limites_requisicoes"
    __table_args__ = (CheckConstraint("tentativas > 0", name="ck_limite_tentativas"),)
    chave: Mapped[str] = mapped_column(String(64), primary_key=True)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False)
