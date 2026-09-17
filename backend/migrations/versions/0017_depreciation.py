"""Add month-based replacement savings backed by managed fund positions."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_depreciation"
down_revision: str | None = "0016_fund_release"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "funds", sa.Column("managed", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.create_table(
        "depreciation_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "fund_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("funds.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("cost", sa.Numeric(20, 4), nullable=False),
        sa.Column("purchase_month", sa.String(7), nullable=False),
        sa.Column("months", sa.Integer(), nullable=False),
        sa.Column("inflation", sa.Numeric(7, 4), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cost > 0", name="ck_depreciation_cost"),
        sa.CheckConstraint("months BETWEEN 1 AND 600", name="ck_depreciation_months"),
        sa.CheckConstraint("inflation BETWEEN 0 AND 100", name="ck_depreciation_inflation"),
        sa.CheckConstraint("version > 0", name="ck_depreciation_version"),
    )
    op.create_table(
        "depreciation_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "purchase_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("depreciation_purchases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fund_events.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False),
    )
    op.create_index(
        "ix_depreciation_receipts_purchase_id", "depreciation_receipts", ["purchase_id"]
    )


def downgrade() -> None:
    op.execute("""DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM depreciation_purchases) THEN
            RAISE EXCEPTION 'Cannot downgrade while depreciation purchases exist';
        END IF;
    END $$""")
    op.drop_table("depreciation_receipts")
    op.drop_table("depreciation_purchases")
    op.drop_column("funds", "managed")
