"""create_seen_jobs_table

Revision ID: b2c3d4e5f6a7
Revises: 9a1b2c3d4e5f
Create Date: 2026-11-07 18:41:00.000000

"""
import hashlib
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.core.clock import utcnow


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "9a1b2c3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "seen_jobs",
        sa.Column("url_hash", sa.String(length=64), primary_key=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_seen_jobs_fingerprint", "seen_jobs", ["fingerprint"], unique=False)
    op.create_index("ix_seen_jobs_last_seen_at", "seen_jobs", ["last_seen_at"], unique=False)

    # Backfill seen_jobs from existing jobs table
    bind = op.get_bind()
    jobs_table = sa.table(
        "jobs",
        sa.column("url", sa.String),
        sa.column("fingerprint", sa.String),
        sa.column("discovered_at", sa.DateTime(timezone=True)),
    )
    seen_jobs_table = sa.table(
        "seen_jobs",
        sa.column("url_hash", sa.String),
        sa.column("fingerprint", sa.String),
        sa.column("first_seen_at", sa.DateTime(timezone=True)),
        sa.column("last_seen_at", sa.DateTime(timezone=True)),
    )
    rows = bind.execute(sa.select(jobs_table.c.url, jobs_table.c.fingerprint, jobs_table.c.discovered_at)).fetchall()
    now = utcnow()
    seen_hashes = set()
    for row in rows:
        if not row.url:
            continue
        url_hash = hashlib.sha256(row.url.encode("utf-8")).hexdigest()
        if url_hash in seen_hashes:
            continue
        seen_hashes.add(url_hash)
        bind.execute(
            seen_jobs_table.insert().values(
                url_hash=url_hash,
                fingerprint=row.fingerprint or "",
                first_seen_at=row.discovered_at or now,
                last_seen_at=row.discovered_at or now,
            )
        )


def downgrade() -> None:
    op.drop_index("ix_seen_jobs_last_seen_at", table_name="seen_jobs")
    op.drop_index("ix_seen_jobs_fingerprint", table_name="seen_jobs")
    op.drop_table("seen_jobs")

