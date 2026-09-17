"""Add explicit fund release events.

Revision ID: 0016_fund_release
Revises: 0015_statement_imports
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0016_fund_release"
down_revision: str | None = "0015_statement_imports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE fund_event_type ADD VALUE IF NOT EXISTS 'fund_release'")


def downgrade() -> None:
    # Never discard financial facts to make an older application accept them.
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM fund_events WHERE type::text = 'fund_release') THEN
            RAISE EXCEPTION 'Cannot downgrade while fund release events exist';
        END IF;
    END $$""")
    # As with 0013, retain unused PostgreSQL enum labels safely.
