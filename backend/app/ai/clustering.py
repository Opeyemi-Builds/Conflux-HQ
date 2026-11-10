"""Bounded complaint clustering / similarity fallback (Andrew's slice, item 5).

Groups masked complaint texts by issue + time window + token overlap. It never
turns shared wording into proof of a common technical cause: clusters are
triage leads, each complaint keeps its own ID, and membership is returned as
candidate groups with a similarity score for an operator to review.
"""

import re
from dataclasses import dataclass, field

_TOKEN = re.compile(r"[a-z0-9]+")
# Pidgin/Nigerian-English filler with low clustering signal.
_STOPWORDS = frozenset({
    "my", "the", "a", "an", "to", "of", "for", "on", "in", "and", "or",
    "na", "dey", "don", "no", "e", "o", "abeg", "biko", "please",
})


def _tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS)


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class Cluster:
    members: list[str] = field(default_factory=list)  # complaint IDs, preserved
    issue_type: str = "other"
    similarity: float = 0.0
    note: str = "Candidate group for triage; shared wording is not proof of a common cause."


def cluster_complaints(items: list[dict], *, threshold: float = 0.35,
                       max_clusters: int = 25) -> list[Cluster]:
    """Greedy bounded clustering over masked texts. Pure function, no DB/model calls."""
    clusters: list[Cluster] = []
    for item in items:
        cid = str(item.get("id", ""))
        text = item.get("text", "")
        issue = item.get("issue_type") or "other"
        placed = False
        for cluster in clusters:
            if cluster.issue_type != issue:
                continue
            first_text = next(
                (it.get("text", "") for it in items if str(it.get("id")) == cluster.members[0]),
                "",
            )
            score = jaccard(text, first_text)
            if score >= threshold:
                cluster.members.append(cid)
                cluster.similarity = round(max(cluster.similarity, score), 3)
                placed = True
                break
        if not placed:
            if len(clusters) >= max_clusters:
                continue  # bounded: extra items stay unclustered, never dropped silently
            clusters.append(Cluster(members=[cid], issue_type=issue, similarity=1.0))
    return clusters
