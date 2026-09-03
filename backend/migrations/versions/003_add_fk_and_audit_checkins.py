"""add fk and audit fields to checkins

Revision ID: 003
Revises: 002
Create Date: 2026-09-01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("checkins", sa.Column("registrado_por", sa.String, nullable=True))
    op.drop_constraint("checkins_membro_id_fkey", "checkins", type_="foreignkey")
    op.create_foreign_key(
        "checkins_membro_id_fkey",
        "checkins",
        "membros",
        ["membro_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("checkins_membro_id_fkey", "checkins", type_="foreignkey")
    op.create_foreign_key(
        "checkins_membro_id_fkey",
        "checkins",
        "membros",
        ["membro_id"],
        ["id"],
    )
    op.drop_column("checkins", "registrado_por")
