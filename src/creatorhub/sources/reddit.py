from __future__ import annotations

from datetime import datetime, timezone

from ..models import TrendItem
from .base import Source, http_client


class RedditSource(Source):
    """Rising + top-of-day posts from the creator's subreddits (public JSON endpoints)."""

    name = "reddit"

    def __init__(self, subreddits: list[str], limit: int = 25):
        self.subreddits = subreddits
        self.limit = limit

    def fetch(self) -> list[TrendItem]:
        out: list[TrendItem] = []
        with http_client() as http:
            for sub in self.subreddits:
                for listing, extra in (("rising", {}), ("top", {"t": "day"})):
                    r = http.get(f"https://www.reddit.com/r/{sub}/{listing}.json", params={"limit": self.limit, **extra})
                    if r.status_code != 200:
                        continue
                    for child in r.json().get("data", {}).get("children", []):
                        p = child["data"]
                        if p.get("stickied"):
                            continue
                        out.append(TrendItem(
                            id=f"reddit:{p['id']}",
                            source=self.name,
                            title=p.get("title", ""),
                            url=f"https://www.reddit.com{p.get('permalink', '')}",
                            summary=(p.get("selftext") or "")[:500],
                            published_at=datetime.fromtimestamp(p["created_utc"], tz=timezone.utc),
                            engagement=p.get("score") or 0,
                            comments=p.get("num_comments") or 0,
                            tags=[f"r/{sub}"],
                        ))
        return out
