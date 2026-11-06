import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow
from app.models.enums import ReversalStatus, TxnChannel, TxnStatus, TxnType, enum_type


class Transaction(Base):
    """Simulated transaction log. In production this is the bank's own data via an adapter."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("bank_id", "reference", name="uq_txn_bank_reference"),
        Index("ix_txn_path_time", "bank_id", "txn_channel", "processor", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    bank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("banks.id"), index=True)
    reference: Mapped[str] = mapped_column(String(64))  # the bank's own transaction reference
    txn_type: Mapped[TxnType] = mapped_column(enum_type(TxnType))
    txn_channel: Mapped[TxnChannel] = mapped_column(enum_type(TxnChannel))
    status: Mapped[TxnStatus] = mapped_column(enum_type(TxnStatus), index=True)
    reversal_status: Mapped[ReversalStatus] = mapped_column(
        enum_type(ReversalStatus), default=ReversalStatus.NONE
    )
    processor: Mapped[str | None] = mapped_column(String(64))  # switch or processor
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    region: Mapped[str | None] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
