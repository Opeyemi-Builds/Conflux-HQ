import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_event(
    db: Session, *, bank_id: uuid.UUID | None, actor: str, action: str, entity_type: str, entity_id: str, details: dict | None = None
) -> AuditLog:
    entry = AuditLog(
        bank_id=bank_id, actor=actor, action=action, entity_type=entity_type, entity_id=str(entity_id), details=details or {}
    )
    db.add(entry)
    return entry
