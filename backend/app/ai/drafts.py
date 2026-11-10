"""Grounded, non-executing draft generation for incident communication."""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai.evidence import build_evidence
from app.ai.guardrails import verify_draft
from app.ai.runtime import active_key, gemini_request, gemini_text
from app.core.config import get_settings
from app.models import Draft, Incident
from app.models.enums import DraftKind, DraftStatus
from app.services.audit import log_event

_PROMPTS = Path(__file__).parent / "prompts"


def _llm_draft_text(prompt_file: str, facts: dict) -> str | None:
    """Generate draft text via configured LLM provider, or return None to use template fallback."""
    settings = get_settings()
    if not active_key(settings):
        return None
    prompt_path = _PROMPTS / prompt_file
    system = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else "Write a concise grounded draft using only the supplied facts."
    user_text = "Facts JSON:\n" + json.dumps(facts, default=str)
    provider = settings.ai_provider.lower().strip()
    try:
        if provider == "maas":
            from app.ai.providers.maas import MaasConfig, chat_completion
            from app.ai.providers.rate_limit import get_limiter
            from app.ai.providers.settings import maas_active, maas_config_from_settings, maas_key_from_settings
            if not maas_active(settings):
                return None
            get_limiter(int(settings.maas_rate_limit_per_minute or 60)).acquire()
            cfg = maas_config_from_settings(settings)
            messages = [
                {"role": "system", "content": system + " Return only the draft text, no JSON, no preamble."},
                {"role": "user", "content": user_text},
            ]
            result = chat_completion(messages, config=cfg,
                                     gateway_key=maas_key_from_settings(settings), json_mode=False)
            text = (result.payload.get("text") or "").strip()
            return text or None
        if provider == "gemini":
            payload = {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user_text}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 400},
            }
            data, _, _ = gemini_request(
                settings.gemini_api_key,
                settings.gemini_model,
                payload,
                settings.gemini_timeout_seconds,
                settings.gemini_max_attempts,
            )
            text = gemini_text(data).strip()
            return text or None

        return None
    except Exception:
        return None


def _grounded_or_fallback(
    db: Session,
    bank_id,
    incident_id,
    kind: DraftKind,
    prompt_file: str,
    template_text: str,
    facts: dict,
    actor: str,
) -> str:
    candidate = _llm_draft_text(prompt_file, facts)
    if not candidate:
        return template_text
    ok, ungrounded = verify_draft(candidate, facts)
    if not ok:
        log_event(
            db,
            bank_id=bank_id,
            actor=actor,
            action="draft_grounding_blocked",
            entity_type="incident",
            entity_id=str(incident_id),
            details={"kind": kind.value, "ungrounded_numbers": ungrounded},
        )
        return template_text
    return candidate


def create_drafts(db: Session, bank_id, incident: Incident, actor: str = "agent") -> list[Draft]:
    existing = db.query(Draft).filter(Draft.incident_id == incident.id).all()
    if existing:
        return existing

    evidence = getattr(incident, "_evidence", None) or build_evidence(db, bank_id, incident)
    cause = incident.likely_cause or "An investigation is still in progress"
    count = incident.complaint_count
    confidence_str = f"{incident.cause_confidence or 0:.2f}"
    facts = {
        "evidence": evidence,
        "incident_id": str(incident.id),
        "issue_type": incident.issue_type.value,
        "complaint_count": count,
        "started_at": incident.started_at.isoformat(),
        "likely_cause": cause,
        "cause_confidence": confidence_str,
    }

    customer_template = (
        f"We are aware of reports from customers affecting {incident.issue_type.value.replace('_', ' ')}. "
        "Our teams are investigating and will share confirmed resolution updates. "
        "No amount or resolution status has been confirmed unless a team member follows up with you directly."
    )
    ticket_template = (
        f"Incident: {incident.issue_type.value}\n"
        f"Complaint count: {count}\n"
        f"Started: {incident.started_at.isoformat()}\n"
        f"Likely cause: {cause}\n"
        f"Confidence: {confidence_str}\n"
        "Evidence: complaint trend and correlated transaction/system records stored in Conflux HQ.\n"
        "Action: verify the affected payment path, review correlated logs, and assign an owner."
    )

    customer_content = _grounded_or_fallback(
        db, bank_id, incident.id, DraftKind.CUSTOMER_MESSAGE, "draft_message.md", customer_template, facts, actor
    )
    ticket_content = _grounded_or_fallback(
        db, bank_id, incident.id, DraftKind.IT_TICKET, "draft_it_ticket.md", ticket_template, facts, actor
    )

    drafts = [
        Draft(
            incident_id=incident.id,
            kind=DraftKind.CUSTOMER_MESSAGE,
            content=customer_content,
            status=DraftStatus.PENDING,
        ),
        Draft(
            incident_id=incident.id,
            kind=DraftKind.IT_TICKET,
            content=ticket_content,
            status=DraftStatus.PENDING,
        ),
    ]

    tx_info = evidence.get("transactions", {})
    propose_reversal = getattr(
        incident,
        "_propose_reversal",
        bool(tx_info.get("matched_complaints", 0) > 0 and tx_info.get("unreversed_failed", 0) > 0),
    )
    if propose_reversal:
        reversal_content = (
            f"Reversal batch review requested for {tx_info.get('unreversed_failed', 0)} failed unreversed "
            f"transactions ({tx_info.get('matched_complaints', 0)} matched customer complaints) on "
            f"{tx_info.get('dominant_processor') or 'affected switch'}. "
            "Guardrail: requires human verification and core-banking settlement sign-off; prototype never executes money movement."
        )
        drafts.append(
            Draft(
                incident_id=incident.id,
                kind=DraftKind.REVERSAL_REQUEST,
                content=reversal_content,
                status=DraftStatus.PENDING,
            )
        )

    db.add_all(drafts)
    db.flush()
    for draft in drafts:
        log_event(
            db,
            bank_id=bank_id,
            actor=actor,
            action="draft_created",
            entity_type="draft",
            entity_id=str(draft.id),
            details={"kind": draft.kind.value},
        )
    db.commit()
    return drafts
