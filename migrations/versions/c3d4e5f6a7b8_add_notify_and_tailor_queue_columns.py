"""add_notify_and_tailor_queue_columns

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-11-07 18:47:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(
            sa.Column("notify_attempts", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_error", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(
            sa.Column("tailor_status", sa.String(length=20), nullable=False, server_default="pending")
        )
        batch_op.create_index("ix_jobs_notify_attempts", ["notify_attempts"], unique=False)
        batch_op.create_index("ix_jobs_next_attempt_at", ["next_attempt_at"], unique=False)
        batch_op.create_index("ix_jobs_tailor_status", ["tailor_status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_index("ix_jobs_tailor_status")
        batch_op.drop_index("ix_jobs_next_attempt_at")
        batch_op.drop_index("ix_jobs_notify_attempts")
        batch_op.drop_column("tailor_status")
        batch_op.drop_column("last_error")
        batch_op.drop_column("next_attempt_at")
        batch_op.drop_column("notify_attempts")

