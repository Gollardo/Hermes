"""Bounded read-side Oracle schedule access; no scenario persistence."""

import sqlalchemy as sa
from alembic import op

revision = "0016_oracle_read_index"
down_revision = "0015_statement_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_occurrences_oracle_due",
        "expected_occurrences",
        ["due_on", "id"],
        postgresql_where=sa.text("status IN ('pending', 'postponed')"),
    )


def downgrade() -> None:
    op.drop_index("ix_occurrences_oracle_due", table_name="expected_occurrences")
