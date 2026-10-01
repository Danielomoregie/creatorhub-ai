"""Cheap, deterministic first-pass scoring. Runs on every item, no API calls.

score (0-100) = relevance (0-60) + momentum (0-25) + freshness (0-15)
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from .models import Profile, TrendItem

# Rough "this is a lot" engagement-per-hour per source, used to normalise momentum.
VELOCITY_SCALE = {"reddit": 50.0, "hackernews": 20.0, "youtube": 20_000.0, "rss": 1.0}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#]+", text.lower()))


def keyword_hits(text: str, keywords: list[str]) -> tuple[float, list[str]]:
    """Exact phrase = 1.0, all words present (any order) = 0.6."""
    low = text.lower()
    words = _words(text)
    total, hits = 0.0, []
    for kw in keywords:
        k = kw.lower().strip()
        if not k:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(k)}(?![a-z0-9])", low):
            total += 1.0
            hits.append(kw)
        elif len(k.split()) > 1 and _words(k) <= words:
            total += 0.6
            hits.append(kw)
    return total, hits


def relevance(item: TrendItem, profile: Profile) -> tuple[float, str | None, list[str]]:
    text = f"{item.title}\n{item.summary}\n{' '.join(item.tags)}"
    best_niche, best_score, best_hits = None, 0.0, []
    for niche in profile.niches:
        s, hits = keyword_hits(text, niche.keywords + [niche.name])
        if s > best_score:
            best_niche, best_score, best_hits = niche.name, s, hits
    # 1 hit ~ 35, 2 hits ~ 50, saturating at 60. Items from hand-picked sources get a small floor
    # so they can still surface as "adjacent niche" candidates.
    rel = 60 * (1 - math.exp(-0.6 * best_score)) if best_score else 5.0
    return rel, best_niche, best_hits


def momentum(item: TrendItem, now: datetime, previous: tuple[int, datetime] | None = None) -> float:
    scale = VELOCITY_SCALE.get(item.source, 10.0)
    age_h = max((now - item.published_at).total_seconds() / 3600, 0.5)
    velocity = item.engagement / age_h
    if previous:
        prev_eng, prev_at = previous
        dt_h = max((now - prev_at).total_seconds() / 3600, 0.25)
        # Recent growth matters more than lifetime average: that's what "taking off" means.
        velocity = max(velocity, (item.engagement - prev_eng) / dt_h * 1.5)
    return 25 * min(1.0, math.log1p(velocity / scale) / math.log1p(4))


def freshness(item: TrendItem, now: datetime) -> float:
    age_h = max((now - item.published_at).total_seconds() / 3600, 0)
    return 15 * math.exp(-age_h / 24)


def score_item(item: TrendItem, profile: Profile, previous: tuple[int, datetime] | None = None,
               now: datetime | None = None, niche_multipliers: dict[str, float] | None = None) -> TrendItem:
    """niche_multipliers come from the creator's own channel stats (see youtube_stats)."""
    now = now or datetime.now(timezone.utc)
    rel, niche, hits = relevance(item, profile)
    if niche and niche_multipliers:
        rel = min(60.0, rel * niche_multipliers.get(niche, 1.0))
    item.score = round(min(100.0, rel + momentum(item, now, previous) + freshness(item, now)), 1)
    item.matched_niche = niche
    item.matched_keywords = hits
    return item
