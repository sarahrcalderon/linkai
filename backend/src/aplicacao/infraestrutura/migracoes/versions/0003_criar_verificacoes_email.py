"""Estrutura de desafios de verificação de e-mail."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "verificacoes_email",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("codigo_hash", sa.String(64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("utilizado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("limite_tentativas", sa.Integer(), nullable=False),
        sa.CheckConstraint("expira_em > criado_em", name="ck_verificacoes_prazo"),
        sa.CheckConstraint("length(codigo_hash) = 64", name="ck_verificacoes_hash"),
        sa.CheckConstraint(
            "limite_tentativas > 0 AND tentativas >= 0 AND tentativas <= limite_tentativas",
            name="ck_verificacoes_tentativas",
        ),
    )
    op.create_index(
        "ix_verificacoes_usuario_criado", "verificacoes_email", ["usuario_id", "criado_em"]
    )
    op.create_index("ix_verificacoes_email_expira_em", "verificacoes_email", ["expira_em"])
    condicao = sa.text("utilizado_em IS NULL AND invalidado_em IS NULL")
    op.create_index(
        "ix_verificacoes_pendente",
        "verificacoes_email",
        ["usuario_id"],
        unique=True,
        postgresql_where=condicao,
        sqlite_where=condicao,
    )


def downgrade() -> None:
    op.drop_table("verificacoes_email")
