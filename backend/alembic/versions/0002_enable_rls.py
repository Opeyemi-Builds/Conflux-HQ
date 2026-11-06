"""Enable row level security on every table (Postgres / Supabase only).

Supabase exposes the public schema through its auto-generated REST API. With RLS enabled and
no policies, that API (anon and authenticated keys) can read nothing. Our backend connects
with the database owner role, which bypasses RLS, so the API keeps working while the tables
stay private to the backend.
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLES = ["banks", "profiles", "transactions", "incidents", "complaints", "drafts", "system_events", "audit_log"]


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY')


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE public."{table}" DISABLE ROW LEVEL SECURITY')
