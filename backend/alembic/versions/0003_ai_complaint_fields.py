"""Add complaint AI extraction fields.

Revision ID: 0003_ai_fields
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_ai_fields"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("complaints", sa.Column("mentioned_time", sa.String(length=64), nullable=True))
    op.add_column("complaints", sa.Column("classification_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("complaints", "classification_confidence")
    op.drop_column("complaints", "mentioned_time")
