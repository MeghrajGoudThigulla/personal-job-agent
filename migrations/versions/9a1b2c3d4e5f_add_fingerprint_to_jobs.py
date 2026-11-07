"""add_fingerprint_to_jobs

Revision ID: 9a1b2c3d4e5f
Revises: 85a9a7693735
Create Date: 2026-11-07 18:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.core.fingerprint import compute_fingerprint


# revision identifiers, used by Alembic.
revision: str = "9a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "85a9a7693735"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.add_column(sa.Column("fingerprint", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_jobs_fingerprint", ["fingerprint"], unique=False)

    # Backfill existing jobs
    bind = op.get_bind()
    jobs_table = sa.table(
        "jobs",
        sa.column("id", sa.Integer),
        sa.column("company", sa.String),
        sa.column("title", sa.String),
        sa.column("location", sa.String),
        sa.column("fingerprint", sa.String),
    )
    rows = bind.execute(sa.select(jobs_table.c.id, jobs_table.c.company, jobs_table.c.title, jobs_table.c.location)).fetchall()
    for row in rows:
        fp = compute_fingerprint(row.company, row.title, row.location)
        bind.execute(
            jobs_table.update().where(jobs_table.c.id == row.id).values(fingerprint=fp)
        )


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_index("ix_jobs_fingerprint")
        batch_op.drop_column("fingerprint")

