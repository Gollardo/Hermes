"""Persist the owner-configured minimum balance buffer.

Revision ID: 0019_minimum_balance_buffer
Revises: 0018_import_provenance
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_minimum_balance_buffer"
down_revision: str | None = "0018_import_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "application_settings",
        sa.Column("minimum_balance_buffer", sa.Numeric(20, 4), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_application_settings_minimum_buffer",
        "application_settings",
        "minimum_balance_buffer >= 0",
    )
    op.alter_column("application_settings", "minimum_balance_buffer", server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        "ck_application_settings_minimum_buffer", "application_settings", type_="check"
    )
    op.drop_column("application_settings", "minimum_balance_buffer")
