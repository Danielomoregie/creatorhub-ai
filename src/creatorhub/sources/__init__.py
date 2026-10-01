"""Trend sources. Each returns a list of TrendItem and must never raise on network trouble."""

from __future__ import annotations

import logging

from ..config import Settings
from ..models import Profile, TrendItem
from .base import Source
from .hackernews import HackerNewsSource
from .reddit import RedditSource
from .rss import RssSource
from .youtube import YouTubeSource

log = logging.getLogger(__name__)


def build_sources(profile: Profile, settings: Settings) -> list[Source]:
    sources: list[Source] = [HackerNewsSource(profile.all_keywords())]
    if profile.sources.subreddits:
        sources.append(RedditSource(profile.sources.subreddits))
    if profile.sources.rss_feeds:
        sources.append(RssSource(profile.sources.rss_feeds))
    if settings.youtube_api_key:
        sources.append(YouTubeSource(settings.youtube_api_key, profile.all_keywords(), profile.sources.youtube_region))
    return sources


def collect(sources: list[Source]) -> list[TrendItem]:
    items: dict[str, TrendItem] = {}
    for src in sources:
        try:
            for item in src.fetch():
                items[item.id] = item
        except Exception as e:  # one flaky source must not kill the scan
            log.warning("source %s failed: %s", src.name, e)
    return list(items.values())


__all__ = ["Source", "build_sources", "collect"]
