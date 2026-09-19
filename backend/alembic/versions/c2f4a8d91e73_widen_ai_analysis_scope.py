"""Widen AI analyses to repository scope.

Revision ID: c2f4a8d91e73
Revises: f1d5bb3861c2
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c2f4a8d91e73"
down_revision: Union[str, Sequence[str], None] = "f1d5bb3861c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CHECK_NAME = "ck_ai_analyses_exactly_one_scope"
_REPOSITORY_FK_NAME = "fk_ai_analyses_repository_id_repositories"
_REPOSITORY_INDEX_NAME = "ix_ai_analyses_repository_id"


def upgrade() -> None:
    with op.batch_alter_table("ai_analyses") as batch_op:
        batch_op.alter_column(
            "finding_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )
        batch_op.add_column(sa.Column("repository_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            _REPOSITORY_FK_NAME,
            "repositories",
            ["repository_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(_REPOSITORY_INDEX_NAME, ["repository_id"], unique=False)
        batch_op.create_check_constraint(
            _CHECK_NAME,
            "(finding_id IS NOT NULL) != (repository_id IS NOT NULL)",
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_analyses") as batch_op:
        batch_op.drop_constraint(_CHECK_NAME, type_="check")
        batch_op.drop_index(_REPOSITORY_INDEX_NAME)
        batch_op.drop_constraint(_REPOSITORY_FK_NAME, type_="foreignkey")
        batch_op.drop_column("repository_id")
        batch_op.alter_column(
            "finding_id",
            existing_type=sa.Uuid(),
            nullable=False,
        )