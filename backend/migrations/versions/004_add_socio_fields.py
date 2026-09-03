"""add socio fields: cpf, senha_hash, email, fone, matricula, socio_gpa_desde, aniversario, cidade, estado, ativo

Revision ID: 004
Revises: 003
Create Date: 2026-09-01
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("membros", sa.Column("cpf", sa.String(11), nullable=True))
    op.add_column("membros", sa.Column("senha_hash", sa.String(255), nullable=True))
    op.add_column("membros", sa.Column("email", sa.String(255), nullable=True))
    op.add_column("membros", sa.Column("fone", sa.String(20), nullable=True))
    op.add_column("membros", sa.Column("matricula_gremio", sa.String(30), nullable=True))
    op.add_column("membros", sa.Column("socio_gpa_desde", sa.DateTime(), nullable=True))
    op.add_column("membros", sa.Column("aniversario", sa.String(20), nullable=True))
    op.add_column("membros", sa.Column("cidade", sa.String(100), nullable=True))
    op.add_column("membros", sa.Column("estado", sa.String(2), nullable=True))
    op.add_column("membros", sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_unique_constraint("uq_membros_cpf", "membros", ["cpf"])
    op.create_index("ix_membros_cpf", "membros", ["cpf"])


def downgrade():
    op.drop_index("ix_membros_cpf", table_name="membros")
    op.drop_constraint("uq_membros_cpf", "membros", type_="unique")
    for col in ["ativo", "estado", "cidade", "aniversario", "socio_gpa_desde",
                "matricula_gremio", "fone", "email", "senha_hash", "cpf"]:
        op.drop_column("membros", col)
