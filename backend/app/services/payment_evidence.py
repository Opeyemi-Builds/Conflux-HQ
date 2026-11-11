"""Pure helpers for deduplicating provider evidence before persistence."""

from collections.abc import Iterable

from typing import TypeAlias
import uuid

from app.adapters.xtradot_schemas import (
    PaymentEvidenceEvent,
    ProviderStatus,
    ReportEvidenceEvent,
)

ProviderEvidence = PaymentEvidenceEvent | ReportEvidenceEvent

EvidenceScope: TypeAlias = tuple[uuid.UUID, str, str, str]


class ProviderEventConflictError(ValueError):
    """Raised when a provider reuses an event ID for different event content."""


def event_deduplication_key(event: ProviderEvidence) -> EvidenceScope:
    """Provider event IDs are unique only inside a bank/provider/environment scope."""
    return (event.bank_id, event.provider, event.environment, event.provider_event_id)


def append_unique_events(
    existing: Iterable[ProviderEvidence],
    incoming: Iterable[ProviderEvidence],
) -> list[ProviderEvidence]:
    """Append unseen provider events without mutating or replacing prior evidence.

    Updates for the same report arrive under a new event ID (snapshot
    semantics), so `report.updated` rows coexist with the `report.ready` row
    they supersede; readers resolve currency by `report_id` at read time.
    """
    result = list(existing)
    seen = {event_deduplication_key(event): event for event in result}
    for event in incoming:
        key = event_deduplication_key(event)
        if key not in seen:
            result.append(event)
            seen[key] = event
            continue
        previous = seen[key]
        previous_content = previous.model_dump(exclude={"id", "received_at"})
        incoming_content = event.model_dump(exclude={"id", "received_at"})
        if previous_content != incoming_content:
            raise ProviderEventConflictError(
                "Provider event ID was replayed with conflicting content"
            )
    return result
