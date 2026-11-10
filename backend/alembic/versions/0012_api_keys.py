"""Add bank-scoped machine API keys for dashboard integrations.

Revision ID: 0012_api_keys
Revises: 0011_xtradot_webhooks
Create Date: 2026-11-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0012_api_keys"
down_revision: Union[str, None] = "0011_xtradot_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bank_id", sa.Uuid(), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("key_prefix", sa.String(12), nullable=False, unique=True),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("demo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_api_keys_bank_status", "api_keys", ["bank_id", "status"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("api_keys")
