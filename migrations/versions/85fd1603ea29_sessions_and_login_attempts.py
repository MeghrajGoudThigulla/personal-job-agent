"""sessions_and_login_attempts

Revision ID: 85fd1603ea29
Revises: 577a145e5715
Create Date: 2026-11-07 17:59:50.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '85fd1603ea29'
down_revision: Union[str, Sequence[str], None] = '577a145e5715'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if "sessions" not in tables:
        op.create_table(
            "sessions",
            sa.Column("sid", sa.String(64), primary_key=True),
            sa.Column("csrf_token", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("client_ip", sa.String(50), nullable=True, server_default=""),
        )

    if "login_attempts" not in tables:
        op.create_table(
            "login_attempts",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("ip_address", sa.String(50), nullable=False, index=True),
            sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, index=True),
            sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    op.drop_table("login_attempts")
    op.drop_table("sessions")
