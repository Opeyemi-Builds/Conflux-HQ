"""Add transactional jobs queue table with PostgreSQL RLS.

Revision ID: 0004_jobs_queue
Revises: 0003_ai_fields
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_jobs_queue"
down_revision = "0003_ai_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bank_id", sa.Uuid(), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "classify_complaint",
                "detect_spikes",
                "investigate_incident",
                "dispatch_approval",
                name="jobkind",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "completed",
                "dead_letter",
                name="jobstatus",
                native_enum=False,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("bank_id", "idempotency_key", name="uq_job_bank_idempotency"),
    )
    op.create_index("ix_jobs_bank_id", "jobs", ["bank_id"])
    op.create_index("ix_jobs_kind", "jobs", ["kind"])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])
    op.create_index("ix_jobs_bank_status_lease", "jobs", ["bank_id", "status", "lease_until"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE jobs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_jobs_bank_status_lease", table_name="jobs")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_index("ix_jobs_kind", table_name="jobs")
    op.drop_index("ix_jobs_bank_id", table_name="jobs")
    op.drop_table("jobs")

