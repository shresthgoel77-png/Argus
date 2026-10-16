"""Add persisted repository monitoring assessment status.

Revision ID: bf7431ce9a12
Revises: 8a4b6c7d8e9f
Create Date: 2026-10-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bf7431ce9a12"
down_revision: Union[str, Sequence[str], None] = "8a4b6c7d8e9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "repositories",
        sa.Column(
            "monitoring_status",
            sa.String(),
            server_default="disabled",
            nullable=False,
        ),
    )
    op.add_column(
        "repositories",
        sa.Column("monitoring_checks", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "repositories",
        sa.Column("last_monitoring_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "ai_analyses",
        sa.Column("key_insights", sa.JSON(), nullable=True),
    )
    op.execute(
        """
        UPDATE repositories
        SET monitoring_status = 'queued',
            monitoring_checks = '{}'
        WHERE monitoring_enabled IS TRUE
        """
    )


def downgrade() -> None:
    op.drop_column("ai_analyses", "key_insights")
    op.drop_column("repositories", "last_monitoring_at")
    op.drop_column("repositories", "monitoring_checks")
    op.drop_column("repositories", "monitoring_status")
