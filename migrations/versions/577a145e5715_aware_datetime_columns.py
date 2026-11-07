"""aware_datetime_columns

Revision ID: 577a145e5715
Revises: 478eff8a7f46
Create Date: 2026-11-07 17:50:35.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '577a145e5715'
down_revision: Union[str, Sequence[str], None] = '478eff8a7f46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.alter_column("discovered_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime(), existing_nullable=True)
        batch_op.alter_column("notified_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime(), existing_nullable=True)

    with op.batch_alter_table("tailored_applications") as batch_op:
        batch_op.alter_column("created_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime(), existing_nullable=True)

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column("timestamp", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime(), existing_nullable=True)

    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.alter_column("updated_at", type_=sa.DateTime(timezone=True), existing_type=sa.DateTime(), existing_nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("app_settings") as batch_op:
        batch_op.alter_column("updated_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True), existing_nullable=True)

    with op.batch_alter_table("audit_logs") as batch_op:
        batch_op.alter_column("timestamp", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True), existing_nullable=True)

    with op.batch_alter_table("tailored_applications") as batch_op:
        batch_op.alter_column("created_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True), existing_nullable=True)

    with op.batch_alter_table("jobs") as batch_op:
        batch_op.alter_column("notified_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True), existing_nullable=True)
        batch_op.alter_column("discovered_at", type_=sa.DateTime(), existing_type=sa.DateTime(timezone=True), existing_nullable=True)
