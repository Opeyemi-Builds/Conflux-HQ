"""Conservative wording groups for investigation. Membership does not establish cause."""
import re
from collections import defaultdict
from datetime import timezone

from app.core.privacy import mask_pii
from app.models import Complaint


def cluster_complaint_wording(complaints: list[Complaint]) -> list[list[str]]:
    groups: dict[tuple, list[str]] = defaultdict(list)
    for complaint in complaints:
        occurred = complaint.occurred_at
        hour = occurred.replace(tzinfo=timezone.utc) if occurred.tzinfo is None else occurred.astimezone(timezone.utc)
        wording = " ".join(re.findall(r"[^\W_]+", mask_pii(complaint.text[:1000]).casefold()))
        if not wording or complaint.issue_type is None:
            continue
        key = (complaint.issue_type, hour.replace(minute=0, second=0, microsecond=0), wording)
        groups[key].append(str(complaint.id))
    return [ids for ids in groups.values() if len(ids) > 1]
