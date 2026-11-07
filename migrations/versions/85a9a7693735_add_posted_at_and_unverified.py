"""add_posted_at_and_unverified

Revision ID: 85a9a7693735
Revises: 85fd1603ea29
Create Date: 2026-11-07 18:22:30.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85a9a7693735'
down_revision: Union[str, Sequence[str], None] = '85fd1603ea29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("posted_date_unverified", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.create_index("ix_jobs_posted_at", ["posted_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_index("ix_jobs_posted_at")
        batch_op.drop_column("posted_date_unverified")
        batch_op.drop_column("posted_at")
