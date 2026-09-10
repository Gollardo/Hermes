"""Statement profiles and durable import receipts."""

import sqlalchemy as sa
from alembic import op

revision = "0015_statement_imports"
down_revision = "0014_one_off_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("mapping", sa.JSON(), nullable=False),
    )
    op.create_table(
        "import_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_key", sa.String(64), nullable=False, unique=True),
        sa.Column("decision_hash", sa.String(64), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=False),
    )


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM import_receipts)")).scalar():
        raise RuntimeError("Import receipts exist; restore a pre-import backup instead")
    op.drop_table("import_receipts")
    op.drop_table("import_profiles")
