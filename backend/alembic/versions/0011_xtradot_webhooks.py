"""Add immutable XtraDot sandbox webhook receipts (Opeyemi-integrated Adfola slice).

Revision ID: 0011_xtradot_webhooks
Revises: 0010_remediation
Create Date: 2026-11-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0011_xtradot_webhooks"
down_revision: Union[str, None] = "0010_remediation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "xtradot_webhook_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bank_id", sa.Uuid(), sa.ForeignKey("banks.id"), nullable=True),
        sa.Column("provider", sa.String(32), nullable=False, server_default="xtradot"),
        sa.Column("environment", sa.String(16), nullable=False, server_default="sandbox"),
        sa.Column("event_id", sa.String(160), nullable=True),
        sa.Column("event_type", sa.String(160), nullable=True),
        sa.Column("raw_body", sa.LargeBinary(), nullable=False),
        sa.Column("raw_timestamp", sa.String(160), nullable=True),
        sa.Column("signature_valid", sa.Boolean(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="received"),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processing_error", sa.String(256), nullable=True),
    )
    op.create_index(
        "uq_xtradot_webhook_scope_event",
        "xtradot_webhook_receipts",
        ["provider", "environment", "event_id"],
        unique=True,
    )
    op.create_index(
        "ix_xtradot_webhook_bank_status_created",
        "xtradot_webhook_receipts",
        ["bank_id", "status", "received_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE xtradot_webhook_receipts ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("xtradot_webhook_receipts")
