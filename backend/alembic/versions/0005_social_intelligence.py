"""Store X engagement and reputation triage signals."""
from alembic import op
import sqlalchemy as sa

revision = "0005_social_intelligence"
down_revision = "0004_jobs_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("social_receipts", sa.Column("public_metrics", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.add_column("social_receipts", sa.Column("reputation_flags", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("social_receipts", sa.Column("reputation_score", sa.Float(), nullable=False, server_default="0"))


def downgrade():
    op.drop_column("social_receipts", "reputation_score")
    op.drop_column("social_receipts", "reputation_flags")
    op.drop_column("social_receipts", "public_metrics")
