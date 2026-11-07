"""Eventos mínimos de acesso sem identificação de visitantes."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eventos_acesso",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "link_id", sa.Uuid(), sa.ForeignKey("links.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("acessado_em", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_eventos_link_instante_id", "eventos_acesso", ["link_id", "acessado_em", "id"]
    )
    op.create_index("ix_eventos_acessado_em", "eventos_acesso", ["acessado_em"])


def downgrade() -> None:
    op.drop_table("eventos_acesso")
