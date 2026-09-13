"""Persist reviewed Oracle workspaces without financial writes."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0017_saved_scenarios"
down_revision = "0016_oracle_read_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_scenarios",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("workspace", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_saved_scenarios_version"),
        sa.CheckConstraint("length(btrim(name)) > 0", name="ck_saved_scenarios_name"),
        sa.CheckConstraint(
            "jsonb_typeof(workspace) = 'object'", name="ck_saved_scenarios_workspace"
        ),
    )


def downgrade() -> None:
    op.drop_table("saved_scenarios")
