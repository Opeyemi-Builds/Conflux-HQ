"""Social intake schema, including RLS for Supabase's direct REST surface."""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("bank_aliases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bank_id", sa.Uuid(), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("value", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("platform", sa.String(16)),
        sa.UniqueConstraint("bank_id", "value", name="uq_bank_alias"))
    op.create_index("ix_bank_aliases_bank_id", "bank_aliases", ["bank_id"])
    op.create_table("social_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bank_id", sa.Uuid(), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("post_id", sa.String(160), nullable=False),
        sa.Column("complaint_id", sa.Uuid(), sa.ForeignKey("complaints.id"), nullable=False),
        sa.Column("source_url", sa.String(500)),
        sa.Column("matched_aliases", sa.JSON(), nullable=False),
        sa.Column("analysis_method", sa.String(32), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("bank_id", "platform", "post_id", name="uq_social_receipt"))
    op.create_index("ix_social_receipts_bank_id", "social_receipts", ["bank_id"])
    if op.get_bind().dialect.name == "postgresql":
        for table in ("bank_aliases", "social_receipts"):
            op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')


def downgrade():
    op.drop_table("social_receipts")
    op.drop_table("bank_aliases")
