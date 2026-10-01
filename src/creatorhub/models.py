from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Niche(BaseModel):
    name: str
    keywords: list[str] = Field(default_factory=list)


class SourceSettings(BaseModel):
    subreddits: list[str] = Field(default_factory=list)
    rss_feeds: list[str] = Field(default_factory=list)
    youtube_region: str = "US"


class AlertSettings(BaseModel):
    min_score: int = 65
    adjacent_niches: bool = True
    max_alerts_per_scan: int = 5


class Profile(BaseModel):
    name: str = "Creator"
    bio: str = ""
    audience: str = ""
    voice: str = ""
    platforms: list[str] = Field(default_factory=list)
    niches: list[Niche] = Field(default_factory=list)
    sources: SourceSettings = Field(default_factory=SourceSettings)
    alerts: AlertSettings = Field(default_factory=AlertSettings)

    def all_keywords(self) -> list[str]:
        return [k for n in self.niches for k in n.keywords]


class TrendItem(BaseModel):
    """One piece of raw signal pulled from a source (a post, video, story...)."""

    id: str  # stable, source-prefixed, e.g. "reddit:abc123"
    source: str
    title: str
    url: str
    summary: str = ""
    published_at: datetime
    engagement: int = 0  # upvotes / points / views, whatever the source counts
    comments: int = 0
    tags: list[str] = Field(default_factory=list)

    # Filled in by scoring
    score: float = 0.0
    matched_niche: str | None = None
    matched_keywords: list[str] = Field(default_factory=list)


class ContentIdea(BaseModel):
    title: str = Field(description="Working title / hook for the piece")
    format: str = Field(description="e.g. 'YouTube long-form', 'TikTok', 'IG carousel', 'LinkedIn post'")
    hook: str = Field(description="The first 3 seconds / first line")
    angle: str = Field(description="Why this, why you, why now")
    outline: list[str] = Field(description="3-6 beats")
    niche: str
    source_trend_ids: list[str] = Field(default_factory=list)


class IdeaBatch(BaseModel):
    ideas: list[ContentIdea]


class TrendAssessment(BaseModel):
    """LLM judgment on whether a trend matters to this creator."""

    trend_id: str
    relevant: bool
    kind: Literal["core", "adjacent", "noise"] = Field(
        description="core = inside an existing niche; adjacent = a new niche the creator could credibly expand into"
    )
    suggested_niche: str = Field(description="Existing niche name, or a short name for the new adjacent niche")
    why_now: str = Field(description="One sentence on why this is worth acting on now")


class TrendAssessmentBatch(BaseModel):
    assessments: list[TrendAssessment]


class Alert(BaseModel):
    id: int | None = None
    kind: Literal["trend", "adjacent_niche", "idea"]
    title: str
    body: str
    trend_id: str | None = None
    url: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    read: bool = False
