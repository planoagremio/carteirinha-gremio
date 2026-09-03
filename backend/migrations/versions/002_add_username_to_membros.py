"""add username to membros

Revision ID: 002
Revises: 001
Create Date: 2026-08-24

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("membros", sa.Column("username", sa.String(60), nullable=True))
    op.create_unique_constraint("uq_membros_username", "membros", ["username"])
    op.create_index("ix_membros_username", "membros", ["username"])


def downgrade() -> None:
    op.drop_index("ix_membros_username", table_name="membros")
    op.drop_constraint("uq_membros_username", "membros", type_="unique")
    op.drop_column("membros", "username")
