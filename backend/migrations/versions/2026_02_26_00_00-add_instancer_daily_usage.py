"""add instancer_daily_usage

Revision ID: 1a2b3c4d5e6f
Revises: 8fb963fca070
Create Date: 2026-02-26 00:00:00.000000+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1a2b3c4d5e6f"
down_revision: str | None = "8fb963fca070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instancer_daily_usage",
        sa.Column("date_utc", sa.Date(), primary_key=True, nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("used_count", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("instancer_daily_usage")

