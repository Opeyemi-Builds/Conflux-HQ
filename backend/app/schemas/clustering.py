import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class ClusterRefreshRequest(BaseModel):
    since: AwareDatetime | None = None
    until: AwareDatetime | None = None

    @model_validator(mode="after")
    def valid_window(self):
        if (self.since is None) != (self.until is None):
            raise ValueError("since and until must be provided together")
        if self.since is not None and self.until is not None and self.since >= self.until:
            raise ValueError("since must be earlier than until")
        return self


class ClusterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    label: str
    label_method: str
    issue_type: str
    payment_category: str | None
    complaint_count: int
    fraud_count: int
    growth_rate: float
    first_seen: datetime
    last_seen: datetime
    channels: dict[str, int]
    regions: dict[str, int]
    related_incident_id: uuid.UUID | None


class ClusterList(BaseModel):
    items: list[ClusterRead]
    total: int


class ClusterSample(BaseModel):
    id: uuid.UUID
    text_masked: str
    channel: str
    region: str | None
    occurred_at: datetime


class ClusterDetail(ClusterRead):
    sample_complaints: list[ClusterSample] = Field(max_length=5)


class ClusterRefreshResponse(BaseModel):
    window_start: datetime
    window_end: datetime
    cluster_count: int
    items: list[ClusterRead]
