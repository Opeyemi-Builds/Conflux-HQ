"""Add human-reviewed fraud, clustering, findings, and draft safety metadata."""
from alembic import op
import sqlalchemy as sa


revision = "0010_ai_intelligence_workstream"
down_revision = "0009_complaint_ai_intelligence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fraud_cases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bank_id", sa.Uuid(), nullable=False),
        sa.Column("complaint_id", sa.Uuid(), nullable=False),
        sa.Column("fraud_type", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("indicators", sa.JSON(), nullable=False),
        sa.Column("repeat_count", sa.Integer(), nullable=False),
        sa.Column("assigned_to", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bank_id"], ["banks.id"]),
        sa.ForeignKeyConstraint(["complaint_id"], ["complaints.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bank_id", "complaint_id", name="uq_fraud_case_bank_complaint"),
    )
    op.create_index("ix_fraud_cases_bank_id", "fraud_cases", ["bank_id"])
    op.create_index("ix_fraud_cases_complaint_id", "fraud_cases", ["complaint_id"])
    op.create_index("ix_fraud_cases_priority", "fraud_cases", ["priority"])
    op.create_index("ix_fraud_cases_status", "fraud_cases", ["status"])
    op.create_index("ix_fraud_cases_bank_status", "fraud_cases", ["bank_id", "status"])
    op.create_index("ix_fraud_cases_bank_priority", "fraud_cases", ["bank_id", "priority"])

    op.create_table(
        "complaint_clusters",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bank_id", sa.Uuid(), nullable=False),
        sa.Column("cluster_key", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=300), nullable=False),
        sa.Column("label_method", sa.String(length=16), nullable=False),
        sa.Column("issue_type", sa.String(length=32), nullable=False),
        sa.Column("payment_category", sa.String(length=32), nullable=True),
        sa.Column("complaint_count", sa.Integer(), nullable=False),
        sa.Column("fraud_count", sa.Integer(), nullable=False),
        sa.Column("growth_rate", sa.Float(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channels", sa.JSON(), nullable=False),
        sa.Column("regions", sa.JSON(), nullable=False),
        sa.Column("related_incident_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bank_id"], ["banks.id"]),
        sa.ForeignKeyConstraint(["related_incident_id"], ["incidents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bank_id", "cluster_key", name="uq_complaint_cluster_bank_key"),
    )
    op.create_index("ix_complaint_clusters_bank_id", "complaint_clusters", ["bank_id"])
    op.create_index("ix_complaint_clusters_payment_category", "complaint_clusters", ["payment_category"])
    op.create_index("ix_complaint_clusters_last_seen", "complaint_clusters", ["last_seen"])
    op.create_index("ix_complaint_clusters_related_incident_id", "complaint_clusters", ["related_incident_id"])
    op.add_column(
        "complaints",
        sa.Column("cluster_id", sa.Uuid(), nullable=True),
    )
    with op.batch_alter_table("complaints") as batch_op:
        batch_op.create_foreign_key(
            "fk_complaints_cluster_id_complaint_clusters",
            "complaint_clusters",
            ["cluster_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_complaints_cluster_id", "complaints", ["cluster_id"])

    op.add_column(
        "incidents",
        sa.Column("investigation_findings", sa.JSON(), nullable=True),
    )
    op.add_column(
        "drafts",
        sa.Column("needs_review", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("drafts", "needs_review")
    op.drop_column("incidents", "investigation_findings")
    op.drop_index("ix_complaints_cluster_id", table_name="complaints")
    with op.batch_alter_table("complaints") as batch_op:
        batch_op.drop_constraint("fk_complaints_cluster_id_complaint_clusters", type_="foreignkey")
    op.drop_column("complaints", "cluster_id")
    op.drop_index("ix_complaint_clusters_last_seen", table_name="complaint_clusters")
    op.drop_index("ix_complaint_clusters_related_incident_id", table_name="complaint_clusters")
    op.drop_index("ix_complaint_clusters_payment_category", table_name="complaint_clusters")
    op.drop_index("ix_complaint_clusters_bank_id", table_name="complaint_clusters")
    op.drop_table("complaint_clusters")
    op.drop_index("ix_fraud_cases_bank_priority", table_name="fraud_cases")
    op.drop_index("ix_fraud_cases_bank_status", table_name="fraud_cases")
    op.drop_index("ix_fraud_cases_status", table_name="fraud_cases")
    op.drop_index("ix_fraud_cases_priority", table_name="fraud_cases")
    op.drop_index("ix_fraud_cases_complaint_id", table_name="fraud_cases")
    op.drop_index("ix_fraud_cases_bank_id", table_name="fraud_cases")
    op.drop_table("fraud_cases")
