"""Cria sessões opacas e revogáveis."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessoes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revogado_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expira_em > criado_em", name="ck_sessoes_expiracao"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_sessoes_hash_tamanho"),
    )
    op.create_index("ix_sessoes_token_hash", "sessoes", ["token_hash"], unique=True)
    op.create_index("ix_sessoes_usuario_id", "sessoes", ["usuario_id"])
    op.create_index("ix_sessoes_expira_em", "sessoes", ["expira_em"])


def downgrade() -> None:
    op.drop_table("sessoes")
