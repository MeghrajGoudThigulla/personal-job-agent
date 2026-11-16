"""add_linkedin_posts_table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-16 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "linkedin_posts",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("post_date", sa.String(length=50), nullable=False, unique=True, index=True),
        sa.Column("theme", sa.String(length=255), nullable=False),
        sa.Column("hook", sa.String(length=512), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("hashtags", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("call_to_action", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("posted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("notified_telegram", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("linkedin_posts")
