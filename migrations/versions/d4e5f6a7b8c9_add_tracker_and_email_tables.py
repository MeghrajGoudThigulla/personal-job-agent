"""add_tracker_and_email_tables

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-16 12:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extend jobs table with Kanban & application tracking fields
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(
            sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("response_received_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("interview_stage", sa.String(length=100), nullable=False, server_default="none")
        )
        batch_op.add_column(
            sa.Column("rejection_reason", sa.String(length=500), nullable=True)
        )
        batch_op.add_column(
            sa.Column("notes", sa.Text(), nullable=False, server_default="")
        )

    # 2. Create interview_rounds table
    op.create_table(
        "interview_rounds",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("round_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("round_type", sa.String(length=100), nullable=False, server_default="technical"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("interviewer_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_interview_rounds_job_id", "interview_rounds", ["job_id"])

    # 3. Create seen_emails table
    op.create_table(
        "seen_emails",
        sa.Column("message_id", sa.String(length=255), primary_key=True),
        sa.Column("account", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("category", sa.String(length=100), nullable=False, server_default="STATUS_UPDATE"),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("seen_emails")
    op.drop_index("ix_interview_rounds_job_id", table_name="interview_rounds")
    op.drop_table("interview_rounds")
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_column("notes")
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("interview_stage")
        batch_op.drop_column("response_received_at")
        batch_op.drop_column("applied_at")
