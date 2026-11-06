"""Outbox criptografada e limites compartilhados."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "outbox_email",
        sa.Column(
            "id",
            sa.Uuid(),
            sa.ForeignKey("verificacoes_email.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("dados_cifrados", sa.Text(), nullable=True),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pendente"),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proxima_tentativa", sa.DateTime(timezone=True), nullable=False),
        sa.Column("arrendado_ate", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posse", sa.Uuid(), nullable=True),
        sa.Column("envio_iniciado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultima_falha", sa.String(40), nullable=True),
        sa.CheckConstraint("tentativas >= 0", name="ck_outbox_tentativas"),
        sa.CheckConstraint(
            "estado IN ('pendente','processando','enviada','falha','indeterminada','cancelada')",
            name="ck_outbox_estado",
        ),
    )
    op.create_index("ix_outbox_prontas", "outbox_email", ["estado", "proxima_tentativa"])
    op.create_index("ix_outbox_email_arrendado_ate", "outbox_email", ["arrendado_ate"])
    op.create_table(
        "limites_requisicoes",
        sa.Column("chave", sa.String(64), primary_key=True),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tentativas", sa.Integer(), nullable=False),
        sa.CheckConstraint("tentativas > 0", name="ck_limite_tentativas"),
    )
    op.create_index("ix_limites_requisicoes_inicio", "limites_requisicoes", ["inicio"])


def downgrade() -> None:
    op.drop_table("limites_requisicoes")
    op.drop_table("outbox_email")
