from typing import Literal
import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import AwareDatetime
from sqlalchemy import func, select

from app.ai.agent import investigate_incident
from app.ai.classifier import classify
from app.ai.clustering import default_cluster_window, refresh_clusters
from app.ai.drafts import create_drafts
from app.ai.eval import evaluate_golden_set
from app.ai.reputation import (
    ALLOWED_REPUTATION_LABELS,
    coordinated_post_ids,
    public_escalation_urgency,
    reputation_signal_index,
    safe_theme_label,
)
from app.api.deps import AuthUser, DbSession, Operator
from app.core.config import get_settings
from app.core.privacy import mask_pii
from app.db.base import utcnow
from app.models import Complaint, ComplaintCluster, Draft, Incident, SocialReceipt
from app.models.enums import DraftKind, DraftStatus, IncidentStatus, JobKind
from app.schemas.ai import (ClassificationResponse, ClassifyRequest, DraftDecision, DraftRead,
                            InvestigationResponse)
from app.schemas.clustering import (
    ClusterDetail,
    ClusterList,
    ClusterRefreshRequest,
    ClusterRefreshResponse,
    ClusterRead,
    ClusterSample,
)
from app.schemas.reputation import ReputationSummary
from app.services.audit import log_event
from app.services.worker import enqueue_job

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/reputation/summary", response_model=ReputationSummary)
def reputation_summary(
    user: AuthUser,
    db: DbSession,
    since: AwareDatetime | None = None,
    until: AwareDatetime | None = None,
):
    now = utcnow()
    window_start = since or (now - timedelta(days=30))
    window_end = until or now
    if window_start >= window_end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "since must be earlier than until")

    rows = db.execute(
        select(SocialReceipt, Complaint, ComplaintCluster)
        .join(Complaint, Complaint.id == SocialReceipt.complaint_id)
        .outerjoin(
            ComplaintCluster,
            (ComplaintCluster.id == Complaint.cluster_id)
            & (ComplaintCluster.bank_id == user.bank_id),
        )
        .where(
            SocialReceipt.bank_id == user.bank_id,
            SocialReceipt.received_at >= window_start,
            SocialReceipt.received_at < window_end,
        )
        .order_by(SocialReceipt.received_at.desc())
    ).all()
    posts = []
    clusters: dict[uuid.UUID, dict] = {}
    for receipt, complaint, cluster in rows:
        if cluster and cluster.complaint_count >= get_settings().cluster_min_size:
            data = clusters.setdefault(cluster.id, {"cluster": cluster, "count": 0})
            data["count"] += 1
        posts.append(
            {
                "id": str(receipt.id),
                "text": complaint.text,
                "received_at": receipt.received_at,
                "author_ref_hash": receipt.author_ref_hash,
                "flags": [
                    label for label in (receipt.reputation_flags or [])
                    if label in ALLOWED_REPUTATION_LABELS
                ],
                "score": float(receipt.reputation_score or 0),
                "metrics": receipt.public_metrics or {},
                "complaint": complaint,
                "cluster": cluster,
            }
        )

    coordinated_ids = coordinated_post_ids(posts)
    flag_counts: dict[str, int] = {}
    indicator_counts: dict[str, int] = {}
    review_posts = []
    for post in posts:
        flags = set(post["flags"])
        for flag in flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
        indicators = []
        if post["id"] in coordinated_ids:
            indicators.append("coordinated_pattern")
        cluster = post["cluster"]
        if cluster and cluster.complaint_count >= get_settings().cluster_min_size:
            indicators.append("repeated_theme")
        sentiment = getattr(post["complaint"].sentiment, "value", post["complaint"].sentiment)
        if "high_reach" in flags and sentiment == "negative":
            indicators.append("high_reach_negative")
        for indicator in indicators:
            indicator_counts[indicator] = indicator_counts.get(indicator, 0) + 1
        engagement = sum(
            max(0, int(post["metrics"].get(key, 0) or 0))
            for key in ("like_count", "retweet_count", "reply_count", "quote_count")
        )
        labels = flags | set(indicators)
        urgency, priority, requires_review = public_escalation_urgency(
            labels, score=post["score"], engagement=engagement
        )
        if requires_review:
            review_posts.append(
                {
                    "text_masked": mask_pii(post["text"]),
                    "engagement": engagement,
                    "flags": sorted(flags),
                    "indicators": sorted(indicators),
                    "urgency": urgency,
                    "priority": priority,
                    "_rank": (priority == "urgent", priority == "high", engagement),
                }
            )

    theme_counts: dict[str, int] = {}
    for data in clusters.values():
        cluster = data["cluster"]
        label = safe_theme_label(cluster.payment_category, cluster.issue_type)
        theme_counts[label] = theme_counts.get(label, 0) + data["count"]

    return ReputationSummary(
        reputation_signal_index=reputation_signal_index(posts),
        heuristic_note="Demo heuristic for public-signal triage; not a legal or reputational verdict.",
        total_posts=len(posts),
        flag_counts=flag_counts,
        indicator_counts=indicator_counts,
        top_repeated_themes=[
            {"label": label, "post_count": count}
            for label, count in sorted(theme_counts.items(), key=lambda item: (-item[1], item[0]))[:10]
        ],
        posts_needing_review=[
            {key: value for key, value in post.items() if not key.startswith("_")}
            for post in sorted(review_posts, key=lambda item: item["_rank"], reverse=True)[:10]
        ],
    )


@router.post("/clusters/refresh", response_model=ClusterRefreshResponse)
def refresh_complaint_clusters(payload: ClusterRefreshRequest, user: Operator, db: DbSession):
    since, until = payload.since, payload.until
    if since is None or until is None:
        since, until = default_cluster_window()
    clusters = refresh_clusters(db, user.bank_id, since=since, until=until)
    log_event(
        db,
        bank_id=user.bank_id,
        actor=str(user.id),
        action="clusters_refreshed",
        entity_type="complaint_cluster",
        entity_id=f"{since.isoformat()}:{until.isoformat()}",
        details={
            "window_start": since.isoformat(),
            "window_end": until.isoformat(),
            "cluster_count": len(clusters),
        },
    )
    db.commit()
    return ClusterRefreshResponse(
        window_start=since,
        window_end=until,
        cluster_count=len(clusters),
        items=[ClusterRead.model_validate(cluster) for cluster in clusters],
    )


@router.get("/clusters", response_model=ClusterList)
def list_complaint_clusters(
    user: AuthUser,
    db: DbSession,
    since: AwareDatetime | None = None,
    until: AwareDatetime | None = None,
    payment_category: str | None = Query(None, max_length=32),
    min_count: int = Query(1, ge=1, le=1000000),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    if since and until and since >= until:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "since must be earlier than until")
    filters = [
        ComplaintCluster.bank_id == user.bank_id,
        ComplaintCluster.complaint_count >= min_count,
    ]
    if payment_category is not None:
        filters.append(ComplaintCluster.payment_category == payment_category)
    if since is not None:
        filters.append(ComplaintCluster.first_seen >= since)
    if until is not None:
        filters.append(ComplaintCluster.first_seen < until)
    total = db.scalar(select(func.count()).select_from(ComplaintCluster).where(*filters)) or 0
    clusters = db.scalars(
        select(ComplaintCluster)
        .where(*filters)
        .order_by(ComplaintCluster.complaint_count.desc(), ComplaintCluster.last_seen.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ClusterList(items=[ClusterRead.model_validate(item) for item in clusters], total=total)


@router.get("/clusters/{cluster_id}", response_model=ClusterDetail)
def get_complaint_cluster(cluster_id: uuid.UUID, user: AuthUser, db: DbSession):
    cluster = db.scalar(
        select(ComplaintCluster).where(
            ComplaintCluster.id == cluster_id,
            ComplaintCluster.bank_id == user.bank_id,
        )
    )
    if cluster is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint cluster not found")
    samples = db.scalars(
        select(Complaint)
        .where(Complaint.bank_id == user.bank_id, Complaint.cluster_id == cluster.id)
        .order_by(Complaint.occurred_at.desc(), Complaint.id)
        .limit(5)
    ).all()
    data = ClusterRead.model_validate(cluster).model_dump()
    data["sample_complaints"] = [
        ClusterSample(
            id=item.id,
            text_masked=item.text,
            channel=item.channel.value,
            region=item.region,
            occurred_at=item.occurred_at,
        )
        for item in samples
    ]
    return data


@router.post("/classify", response_model=ClassificationResponse)
def classify_text(payload: ClassifyRequest, user: Operator, db: DbSession):
    result, source = classify(payload.text, payload.channel)
    data = result.model_dump()
    data["issue_type"] = result.issue_type.value if hasattr(result.issue_type, "value") else result.issue_type
    runtime = getattr(result, "_runtime", {})
    if result.is_fraud:
        review_status, routing_queue = "needs_review", "fraud_security"
    elif result.confidence < get_settings().classification_review_threshold:
        review_status, routing_queue = "needs_review", "human_review"
    else:
        review_status, routing_queue = "auto", "standard"
    data.update({"source": source, "review_status": review_status, "routing_queue": routing_queue, **runtime})
    from app.services.audit import log_event
    log_event(db, bank_id=user.bank_id, actor=str(user.id), action="text_classified", entity_type="ai_classifier",
              entity_id="paste", details={runtime_key: runtime_value for runtime_key, runtime_value in runtime.items()
                                           if runtime_key != "source"})
    db.commit()
    return data


def _incident(db, incident_id: uuid.UUID, bank_id: uuid.UUID) -> Incident:
    incident = db.get(Incident, incident_id)
    if not incident or incident.bank_id != bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Incident not found")
    return incident


@router.post("/incidents/{incident_id}/investigate", response_model=InvestigationResponse)
def investigate(incident_id: uuid.UUID, user: Operator, db: DbSession):
    incident = _incident(db, incident_id, user.bank_id)
    incident.status = IncidentStatus.INVESTIGATING
    db.commit()
    incident = investigate_incident(db, user.bank_id, incident, actor=str(user.id))
    drafts = create_drafts(db, user.bank_id, incident, actor=str(user.id))
    findings = incident.investigation_findings or {}
    return InvestigationResponse(incident_id=incident.id, likely_cause=incident.likely_cause,
                                 cause_confidence=incident.cause_confidence, summary=incident.summary,
                                 draft_count=len(drafts), source=getattr(incident, "_ai_source", "rules"),
                                 model=getattr(incident, "_ai_model", None),
                                 prompt_version=getattr(incident, "_ai_prompt_version", None),
                                 latency_ms=getattr(incident, "_ai_latency_ms", None),
                                 input_tokens=getattr(incident, "_ai_input_tokens", 0),
                                 output_tokens=getattr(incident, "_ai_output_tokens", 0),
                                 confidence=findings.get("confidence"),
                                 supporting_evidence=findings.get("supporting_evidence", []),
                                 contradicting_evidence=findings.get("contradicting_evidence", []),
                                 affected_systems=findings.get("affected_systems", []),
                                 affected_channels=findings.get("affected_channels", []),
                                 recommended_owner=findings.get("recommended_owner"),
                                 recommended_next_step=findings.get("recommended_next_step"),
                                 method=findings.get("method", getattr(incident, "_ai_method", "rules_fallback")))


@router.get("/incidents/{incident_id}/drafts", response_model=list[DraftRead])
def list_drafts(incident_id: uuid.UUID, user: Operator, db: DbSession):
    _incident(db, incident_id, user.bank_id)
    return db.execute(select(Draft).join(Incident).where(Incident.bank_id == user.bank_id,
                                                         Draft.incident_id == incident_id)).scalars().all()


@router.post("/drafts/{draft_id}/decision", response_model=DraftRead)
def decide_draft(draft_id: uuid.UUID, payload: DraftDecision, user: Operator, db: DbSession):
    if payload.decision not in (DraftStatus.APPROVED, DraftStatus.REJECTED):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Decision must be approved or rejected")
    draft = db.get(Draft, draft_id)
    if not draft:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    incident = db.get(Incident, draft.incident_id)
    if not incident or incident.bank_id != user.bank_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Draft not found")
    if draft.status != DraftStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Draft has already been decided")
    if payload.decision == DraftStatus.APPROVED and draft.kind == DraftKind.REVERSAL_REQUEST:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Reversals cannot be executed by this prototype")

    draft.status = payload.decision
    draft.decided_by = str(user.id)
    draft.decided_at = utcnow()
    all_drafts = db.execute(select(Draft).where(Draft.incident_id == incident.id)).scalars().all()
    if all(d.status == DraftStatus.APPROVED for d in all_drafts):
        incident.status = IncidentStatus.RESOLVED

    log_event(db, bank_id=user.bank_id, actor=str(user.id), action="draft_decided", entity_type="draft",
              entity_id=str(draft.id), details={"decision": payload.decision.value, "kind": draft.kind.value})
    if payload.decision == DraftStatus.APPROVED:
        enqueue_job(
            db,
            bank_id=user.bank_id,
            kind=JobKind.DISPATCH_APPROVAL,
            payload={"draft_id": str(draft.id), "incident_id": str(incident.id), "kind": draft.kind.value},
            idempotency_key=f"outbox:draft:{draft.id}",
        )
    db.commit()
    return draft


@router.get("/audit")
def bank_audit(user: AuthUser, db: DbSession, limit: int = Query(100, ge=1, le=500)):
    from app.models import AuditLog
    rows = db.execute(
        select(AuditLog)
        .where(AuditLog.bank_id == user.bank_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return [
        {
            "id": str(row.id),
            "actor": row.actor,
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "details": row.details,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/incidents/{incident_id}/audit")
def incident_audit(incident_id: uuid.UUID, user: Operator, db: DbSession):
    _incident(db, incident_id, user.bank_id)
    from app.models import AuditLog
    rows = db.execute(select(AuditLog).where(AuditLog.bank_id == user.bank_id,
                                            AuditLog.entity_id == str(incident_id))
                      .order_by(AuditLog.created_at)).scalars().all()
    return [{"id": str(row.id), "actor": row.actor, "action": row.action,
             "entity_type": row.entity_type, "entity_id": row.entity_id,
             "details": row.details, "created_at": row.created_at} for row in rows]


@router.get("/evaluate")
def evaluate_classifier(
    user: AuthUser,
    mode: Literal["rules", "auto"] = Query(default="rules", description="Evaluate deterministic fallback rules or active LLM provider against the 100-item golden set."),
):
    return evaluate_golden_set(mode=mode)
