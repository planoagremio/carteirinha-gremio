"""initial

Revision ID: 001
Revises:
Create Date: 2026-08-20

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "membros",
        sa.Column("id", sa.String(30), primary_key=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("doc", sa.String(100), nullable=True),
        sa.Column("foto", sa.Text, nullable=True),
        sa.Column("criado_em", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "checkins",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("membro_id", sa.String(30), sa.ForeignKey("membros.id"), nullable=False, index=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("date", sa.String(10), nullable=False, index=True),
        sa.Column("time", sa.String(5), nullable=False),
        sa.Column("ts", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("checkins")
    op.drop_table("membros")
