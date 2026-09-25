"""Add a unique index for external user identity mappings.

Revision ID: 8a4b6c7d8e9f
Revises: 6dbcd9a73647
Create Date: 2026-09-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "8a4b6c7d8e9f"
down_revision: Union[str, Sequence[str], None] = "6dbcd9a73647"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_users_external_auth_id",
        "users",
        ["external_auth_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_users_external_auth_id", table_name="users")