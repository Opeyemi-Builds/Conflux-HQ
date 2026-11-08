"""Create human-reviewed payment proposal records."""
from alembic import op
import sqlalchemy as sa

revision = "0008_payment_proposals"
down_revision = "0007_payment_exceptions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_proposals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bank_id", sa.Uuid(), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("exception_id", sa.Uuid(), sa.ForeignKey("payment_exceptions.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("proposed_by", sa.String(64), nullable=False),
        sa.Column("decided_by", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_payment_proposals_bank_id", "payment_proposals", ["bank_id"])
    op.create_index("ix_payment_proposals_exception_id", "payment_proposals", ["exception_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE payment_proposals ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_index("ix_payment_proposals_exception_id", table_name="payment_proposals")
    op.drop_index("ix_payment_proposals_bank_id", table_name="payment_proposals")
    op.drop_table("payment_proposals")
