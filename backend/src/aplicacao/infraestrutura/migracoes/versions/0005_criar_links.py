"""Links personalizados com unicidade global e exclusão lógica."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Uuid(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("numero_whatsapp", sa.String(16), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("excluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("slug", name="uq_links_slug"),
        sa.CheckConstraint(
            "length(nome) BETWEEN 2 AND 100 AND nome = trim(nome)", name="ck_links_nome"
        ),
        sa.CheckConstraint(
            "length(slug) BETWEEN 3 AND 64 AND slug = lower(trim(slug))", name="ck_links_slug"
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_links_slug_formato"
        ).ddl_if(dialect="postgresql"),
        sa.CheckConstraint(
            "numero_whatsapp ~ '^\\+[1-9][0-9]{7,14}$'", name="ck_links_numero"
        ).ddl_if(dialect="postgresql"),
        sa.CheckConstraint(
            "slug NOT IN ('api','admin','login','logout','cadastro','dashboard',"
            "'verificar-email','reenviar-codigo','static','assets','docs',"
            "'redoc','openapi','saude','www')",
            name="ck_links_slug_reservado",
        ),
        sa.CheckConstraint(
            "mensagem IS NULL OR (length(mensagem) <= 2000 "
            "AND mensagem NOT LIKE '%<%' AND mensagem NOT LIKE '%>%')",
            name="ck_links_mensagem",
        ),
        sa.CheckConstraint("atualizado_em >= criado_em", name="ck_links_datas"),
        sa.CheckConstraint(
            "excluido_em IS NULL OR (ativo = false AND excluido_em >= criado_em "
            "AND excluido_em <= atualizado_em)",
            name="ck_links_exclusao",
        ),
    )
    op.create_index("ix_links_usuario_criado", "links", ["usuario_id", "criado_em"])


def downgrade() -> None:
    op.drop_table("links")
