"""Retain narrow statement source provenance.

Revision ID: 0018_import_provenance
Revises: 0017_auth_admission
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_import_provenance"
down_revision: str | None = "0017_auth_admission"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("import_receipts", sa.Column("source_date", sa.Date(), nullable=True))
    op.add_column(
        "import_receipts", sa.Column("source_description", sa.String(4000), nullable=True)
    )


def downgrade() -> None:
    # Never silently discard provenance that an older application cannot represent.
    has_provenance = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT EXISTS (SELECT 1 FROM import_receipts "
                "WHERE source_date IS NOT NULL OR source_description IS NOT NULL)"
            )
        )
        .scalar()
    )
    if has_provenance:
        raise RuntimeError("Import provenance exists; restore a pre-import backup instead")
    op.drop_column("import_receipts", "source_description")
    op.drop_column("import_receipts", "source_date")
