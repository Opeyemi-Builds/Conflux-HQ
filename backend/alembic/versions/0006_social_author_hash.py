"""Store a privacy-preserving author identity for social analytics."""
from alembic import op
import sqlalchemy as sa

revision = "0006_social_author_hash"
down_revision = "0005_social_intelligence"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("social_receipts", sa.Column("author_ref_hash", sa.String(length=128), nullable=True))


def downgrade():
    op.drop_column("social_receipts", "author_ref_hash")
