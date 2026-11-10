"""Add corrective actions and persisted investigation runs.

Revision ID: 0010_remediation
Revises: 0009_bank_ingestion
Create Date: 2026-11-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0010_remediation"
down_revision: Union[str, None] = "0009_bank_ingestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "corrective_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bank_id", sa.Uuid(), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(128), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="proposed"),
        sa.Column("bank_confirmed_cause", sa.Text(), nullable=True),
        sa.Column("change_reference", sa.String(128), nullable=True),
        sa.Column("validation_plan", sa.Text(), nullable=True),
        sa.Column("validation_observation", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("verified_by", sa.String(64), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_corrective_actions_bank_status", "corrective_actions", ["bank_id", "status", "created_at"]
    )
    op.create_index(
        "ix_corrective_actions_incident", "corrective_actions", ["incident_id", "status"]
    )

    op.create_table(
        "investigation_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("bank_id", sa.Uuid(), sa.ForeignKey("banks.id"), nullable=False),
        sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="requested"),
        sa.Column("requested_by", sa.String(64), nullable=False),
        sa.Column("model", sa.String(64), nullable=True),
        sa.Column("provider", sa.String(32), nullable=True),
        sa.Column("prompt_version", sa.String(64), nullable=True),
        sa.Column("evidence_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("facts", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("hypotheses", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("missing_evidence", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("recommended_checks", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("recommended_owner", sa.String(128), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_investigation_runs_bank_status", "investigation_runs", ["bank_id", "status", "created_at"]
    )
    op.create_index(
        "ix_investigation_runs_incident", "investigation_runs", ["incident_id", "created_at"]
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE corrective_actions ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE investigation_runs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_table("investigation_runs")
    op.drop_table("corrective_actions")
