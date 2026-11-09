"""Bank complaint ingestion API routes, connector management, and receipt queries."""
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.deps import AdminUser, AuthUser, DbSession
from app.db.base import utcnow
from app.models.ingestion import ComplaintReceipt, IngestionConnector
from app.schemas.ingestion import (
    ComplaintIngestIn,
    ComplaintIngestResponse,
    ComplaintReceiptRead,
    ConnectorCreateIn,
    ConnectorCreateResponse,
    ConnectorRead,
)
from app.services.audit import log_event
from app.services.bank_intake import (
    generate_connector_token,
    ingest_bank_complaint,
    verify_connector_token,
)

router = APIRouter(prefix="/ingestion", tags=["bank complaint ingestion"])


def get_connector(
    db: DbSession,
    authorization: str | None = Header(default=None),
) -> IngestionConnector:
    """Dependency extracting and authenticating the bank connector token."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.removeprefix("Bearer ").strip()
    return verify_connector_token(db, token)


@router.post(
    "/complaints",
    response_model=ComplaintIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a synthetic or live complaint ticket from bank support systems",
)
def ingest_complaint(
    payload: ComplaintIngestIn,
    response: Response,
    db: DbSession,
    connector: IngestionConnector = Depends(get_connector),
):
    """Deliver a complaint ticket with database-enforced idempotency.
    
    Returns 202 on initial acceptance, 200 on identical replay, or 409 on conflicting replay.
    """
    status_code, result = ingest_bank_complaint(db, connector, payload)
    response.status_code = status_code
    return result


@router.post(
    "/connectors",
    response_model=ConnectorCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision a new connector credential bound to the current bank (Admin only)",
)
def create_connector(payload: ConnectorCreateIn, admin: AdminUser, db: DbSession):
    prefix, token, key_hash = generate_connector_token()
    now = utcnow()
    connector = IngestionConnector(
        bank_id=admin.bank_id,
        name=payload.name,
        source_system=payload.source_system,
        key_prefix=prefix,
        key_hash=key_hash,
        status="active",
        synthetic=payload.synthetic,
        created_at=now,
    )
    db.add(connector)
    log_event(
        db,
        bank_id=admin.bank_id,
        actor=str(admin.id),
        action="ingestion_connector_created",
        entity_type="ingestion_connector",
        entity_id=prefix,
        details={"name": payload.name, "source_system": payload.source_system},
    )
    db.commit()
    return {
        "id": connector.id,
        "name": connector.name,
        "source_system": connector.source_system,
        "key_prefix": connector.key_prefix,
        "token": token,
        "created_at": connector.created_at,
    }


@router.get(
    "/connectors",
    response_model=list[ConnectorRead],
    summary="List active and revoked connectors for the current bank",
)
def list_connectors(admin: AdminUser, db: DbSession):
    return db.scalars(
        select(IngestionConnector)
        .where(IngestionConnector.bank_id == admin.bank_id)
        .order_by(IngestionConnector.created_at.desc())
    ).all()


@router.post(
    "/connectors/{connector_id}/revoke",
    response_model=ConnectorRead,
    summary="Revoke a connector credential immediately",
)
def revoke_connector(connector_id: uuid.UUID, admin: AdminUser, db: DbSession):
    connector = db.get(IngestionConnector, connector_id)
    if connector is None or connector.bank_id != admin.bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connector not found")

    connector.status = "revoked"
    connector.revoked_at = utcnow()
    log_event(
        db,
        bank_id=admin.bank_id,
        actor=str(admin.id),
        action="ingestion_connector_revoked",
        entity_type="ingestion_connector",
        entity_id=connector.key_prefix,
    )
    db.commit()
    return connector


@router.get(
    "/receipts",
    response_model=list[ComplaintReceiptRead],
    summary="List complaint intake receipts for the current bank",
)
def list_receipts(
    user: AuthUser,
    db: DbSession,
    external_id: str | None = None,
    payment_reference: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    q = select(ComplaintReceipt).where(ComplaintReceipt.bank_id == user.bank_id)
    if external_id:
        q = q.where(ComplaintReceipt.external_id == external_id)
    if payment_reference:
        q = q.where(ComplaintReceipt.payment_reference == payment_reference)
    return db.scalars(q.order_by(ComplaintReceipt.received_at.desc()).limit(limit).offset(offset)).all()


@router.get(
    "/receipts/{receipt_id}",
    response_model=ComplaintReceiptRead,
    summary="Retrieve an intake receipt by ID",
)
def get_receipt(receipt_id: uuid.UUID, user: AuthUser, db: DbSession):
    receipt = db.get(ComplaintReceipt, receipt_id)
    if receipt is None or receipt.bank_id != user.bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Receipt not found")
    return receipt

