"""Add payment-specific complaint classification fields.

Revision ID: 0009_complaint_ai_intelligence
Revises: 0008_payment_proposals
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_complaint_ai_intelligence"
down_revision = "0008_payment_proposals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("complaints", sa.Column("payment_category", sa.String(length=32), nullable=True))
    op.add_column("complaints", sa.Column("classification_explanation", sa.Text(), nullable=True))
    op.add_column(
        "complaints",
        sa.Column("evidence_phrases", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "complaints",
        sa.Column("review_status", sa.String(length=16), nullable=False, server_default="auto"),
    )
    op.add_column(
        "complaints",
        sa.Column("routing_queue", sa.String(length=24), nullable=False, server_default="standard"),
    )
    op.create_index("ix_complaints_payment_category", "complaints", ["payment_category"])


def downgrade() -> None:
    op.drop_index("ix_complaints_payment_category", table_name="complaints")
    op.drop_column("complaints", "routing_queue")
    op.drop_column("complaints", "review_status")
    op.drop_column("complaints", "evidence_phrases")
    op.drop_column("complaints", "classification_explanation")
    op.drop_column("complaints", "payment_category")
