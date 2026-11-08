"""Create payment exception records."""
from alembic import op
import sqlalchemy as sa

revision = "0007_payment_exceptions"
down_revision = "0006_social_author_hash"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_exceptions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bank_id", sa.Uuid(), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("complaint_id", sa.Uuid(), sa.ForeignKey("complaints.id"), nullable=True),
        sa.Column("transaction_id", sa.Uuid(), sa.ForeignKey("transactions.id"), nullable=True),
        sa.Column("exception_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("settlement_status", sa.String(32), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="NGN"),
        sa.Column("transaction_reference", sa.String(64)),
        sa.Column("processor", sa.String(64)),
        sa.Column("payment_channel", sa.String(32)),
        sa.Column("customer_ref_hash", sa.String(128)),
        sa.Column("match_confidence", sa.Numeric(4, 3)),
        sa.Column("evidence_summary", sa.Text()),
        sa.Column("owner", sa.String(128)),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_payment_exceptions_bank_id", "payment_exceptions", ["bank_id"])
    op.create_index("ix_payment_exceptions_complaint_id", "payment_exceptions", ["complaint_id"])
    op.create_index("ix_payment_exceptions_transaction_id", "payment_exceptions", ["transaction_id"])
    op.create_index("ix_payment_exceptions_bank_status", "payment_exceptions", ["bank_id", "status", "created_at"])
    op.create_index("ix_payment_exceptions_bank_type", "payment_exceptions", ["bank_id", "exception_type", "created_at"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE payment_exceptions ENABLE ROW LEVEL SECURITY")


def downgrade():
    op.drop_index("ix_payment_exceptions_bank_type", table_name="payment_exceptions")
    op.drop_index("ix_payment_exceptions_bank_status", table_name="payment_exceptions")
    op.drop_index("ix_payment_exceptions_transaction_id", table_name="payment_exceptions")
    op.drop_index("ix_payment_exceptions_complaint_id", table_name="payment_exceptions")
    op.drop_index("ix_payment_exceptions_bank_id", table_name="payment_exceptions")
    op.drop_table("payment_exceptions")
