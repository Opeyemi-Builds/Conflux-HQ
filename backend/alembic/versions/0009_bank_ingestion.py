"""Add bank complaint ingestion connectors and receipts.

Revision ID: 0009_bank_ingestion
Revises: 0008_payment_proposals
Create Date: 2026-11-09 21:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0009_bank_ingestion"
down_revision: Union[str, None] = "0008_payment_proposals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create ingestion_connectors table
    op.create_table(
        "ingestion_connectors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bank_id", sa.Uuid(), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("source_system", sa.String(32), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False, unique=True),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("synthetic", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ingestion_connectors_bank_status", "ingestion_connectors", ["bank_id", "status"])

    # 2. Add payment_reference column to complaints
    with op.batch_alter_table("complaints") as batch_op:
        batch_op.add_column(sa.Column("payment_reference", sa.String(64), nullable=True))
        batch_op.create_index("ix_complaints_payment_ref", ["payment_reference"])

    # 3. Create complaint_receipts table
    op.create_table(
        "complaint_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bank_id", sa.Uuid(), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("connector_id", sa.Uuid(), sa.ForeignKey("ingestion_connectors.id"), nullable=False),
        sa.Column("complaint_id", sa.Uuid(), sa.ForeignKey("complaints.id"), nullable=False, unique=True),
        sa.Column("source_system", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("payment_reference", sa.String(64), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synthetic", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.UniqueConstraint("bank_id", "connector_id", "external_id", name="uq_receipt_bank_connector_external"),
    )
    op.create_index("ix_receipt_bank_payment_ref", "complaint_receipts", ["bank_id", "payment_reference"])
    op.create_index("ix_receipt_bank_received", "complaint_receipts", ["bank_id", "received_at"])

    # Enable RLS if PostgreSQL
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE ingestion_connectors ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE complaint_receipts ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("complaint_receipts")

    with op.batch_alter_table("complaints") as batch_op:
        batch_op.drop_index("ix_complaints_payment_ref")
        batch_op.drop_column("payment_reference")

    op.drop_table("ingestion_connectors")

