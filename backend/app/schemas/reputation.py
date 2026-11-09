from pydantic import BaseModel, Field


class ReputationPostRead(BaseModel):
    text_masked: str
    engagement: int
    flags: list[str]
    indicators: list[str]
    urgency: str
    priority: str


class RepeatedThemeRead(BaseModel):
    label: str
    post_count: int


class ReputationSummary(BaseModel):
    reputation_signal_index: float = Field(ge=0, le=100)
    heuristic_note: str
    total_posts: int
    flag_counts: dict[str, int]
    indicator_counts: dict[str, int]
    top_repeated_themes: list[RepeatedThemeRead]
    posts_needing_review: list[ReputationPostRead] = Field(max_length=10)
