"""Separate anonymous source throttles from sensitive owner reauthentication.

Revision ID: 0017_auth_admission
Revises: 0016_fund_release
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_auth_admission"
down_revision: str | None = "0016_fund_release"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("auth_login_throttle", sa.Column("next_login_at", sa.DateTime(timezone=True)))
    op.create_table(
        "auth_client_login_throttle",
        sa.Column("client_hash", sa.String(64), primary_key=True),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True)),
        sa.Column("blocked_until", sa.DateTime(timezone=True)),
        sa.CheckConstraint("failed_count >= 0", name="ck_auth_client_throttle_failed_count"),
    )
    # Legacy failures came from anonymous callers; do not import their block
    # into the now exclusively authenticated sensitive-action budget.
    op.execute(
        "UPDATE auth_login_throttle SET failed_count = 0, "
        "window_started_at = NULL, blocked_until = NULL"
    )


def downgrade() -> None:
    op.drop_table("auth_client_login_throttle")
    op.drop_column("auth_login_throttle", "next_login_at")
