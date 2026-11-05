"""Cria persist?ncia de usu?rios."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("senha_hash", sa.String(512), nullable=False),
        sa.Column("email_verificado", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("email = lower(trim(email))", name="ck_usuarios_email_normalizado"),
        sa.CheckConstraint("length(email) BETWEEN 1 AND 254", name="ck_usuarios_email_tamanho"),
        sa.CheckConstraint("length(trim(nome)) BETWEEN 2 AND 100", name="ck_usuarios_nome_tamanho"),
        sa.CheckConstraint("length(senha_hash) BETWEEN 1 AND 512", name="ck_usuarios_hash_tamanho"),
    )
    op.create_index("ix_usuarios_email", "usuarios", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    op.drop_table("usuarios")
