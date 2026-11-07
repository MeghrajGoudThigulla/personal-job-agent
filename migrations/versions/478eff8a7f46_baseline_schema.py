"""baseline_schema

Revision ID: 478eff8a7f46
Revises:
Create Date: 2026-11-07 17:42:28.377491

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '478eff8a7f46'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "jobs" not in tables:
        op.create_table(
            "jobs",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("title", sa.String(512), nullable=False, index=True),
            sa.Column("company", sa.String(255), nullable=False, index=True),
            sa.Column("location", sa.String(512), nullable=True, server_default="Unknown"),
            sa.Column("remote_status", sa.String(100), nullable=True, server_default="Unknown"),
            sa.Column("role_category", sa.String(255), nullable=True, server_default="Software Engineering"),
            sa.Column("url", sa.String(1024), unique=True, nullable=False, index=True),
            sa.Column("source_platform", sa.String(100), nullable=False, index=True),
            sa.Column("description", sa.Text(), nullable=True, server_default=""),
            sa.Column("posted_date", sa.String(100), nullable=True, server_default=""),
            sa.Column("discovered_at", sa.DateTime(), nullable=True, index=True),
            sa.Column("match_score", sa.Float(), nullable=True, server_default="0.0", index=True),
            sa.Column("match_tier", sa.String(100), nullable=True, server_default="P1", index=True),
            sa.Column("match_reason", sa.Text(), nullable=True, server_default="{}"),
            sa.Column("status", sa.String(100), nullable=True, server_default="new", index=True),
            sa.Column("notified", sa.Boolean(), nullable=True, server_default=sa.false(), index=True),
            sa.Column("notified_at", sa.DateTime(), nullable=True),
        )

    if "tailored_applications" not in tables:
        op.create_table(
            "tailored_applications",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), unique=True, nullable=False),
            sa.Column("tailored_resume_tex", sa.Text(), nullable=True, server_default=""),
            sa.Column("tailored_resume_md", sa.Text(), nullable=True, server_default=""),
            sa.Column("pdf_path", sa.String(512), nullable=True, server_default=""),
            sa.Column("cold_email_hr", sa.Text(), nullable=True, server_default=""),
            sa.Column("cold_email_hiring_manager", sa.Text(), nullable=True, server_default=""),
            sa.Column("linkedin_4mm", sa.Text(), nullable=True, server_default=""),
            sa.Column("slop_score", sa.Float(), nullable=True, server_default="0.0"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
        )

    if "audit_logs" not in tables:
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("timestamp", sa.DateTime(), nullable=True, index=True),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("details", sa.Text(), nullable=True, server_default=""),
            sa.Column("status", sa.String(50), nullable=True, server_default="success"),
        )

    if "app_settings" not in tables:
        op.create_table(
            "app_settings",
            sa.Column("key", sa.String(100), primary_key=True),
            sa.Column("value", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    # For existing databases, ensure column sizes are widened
    if "jobs" in tables:
        with op.batch_alter_table("jobs") as batch_op:
            batch_op.alter_column("match_tier", type_=sa.String(100), existing_type=sa.String(10), nullable=True)
            batch_op.alter_column("title", type_=sa.String(512), existing_type=sa.String(255), nullable=False)
            batch_op.alter_column("location", type_=sa.String(512), existing_type=sa.String(255), nullable=True)
            batch_op.alter_column("role_category", type_=sa.String(255), existing_type=sa.String(100), nullable=True)
            batch_op.alter_column("url", type_=sa.String(1024), existing_type=sa.String(512), nullable=False)
            batch_op.alter_column("remote_status", type_=sa.String(100), existing_type=sa.String(50), nullable=True)
            batch_op.alter_column("status", type_=sa.String(100), existing_type=sa.String(50), nullable=True)


def downgrade() -> None:
    op.drop_table("app_settings")
    op.drop_table("audit_logs")
    op.drop_table("tailored_applications")
    op.drop_table("jobs")
