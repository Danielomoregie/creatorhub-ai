from __future__ import annotations

import time
from datetime import datetime, timezone

from ..models import TrendItem
from .base import Source, http_client

API = "https://hn.algolia.com/api/v1/search_by_date"


class HackerNewsSource(Source):
    """Searches recent HN stories for each of the creator's keywords (Algolia API, no key needed)."""

    name = "hackernews"

    def __init__(self, keywords: list[str], hours: int = 48, per_keyword: int = 10):
        self.keywords = keywords
        self.hours = hours
        self.per_keyword = per_keyword

    def fetch(self) -> list[TrendItem]:
        since = int(time.time()) - self.hours * 3600
        out: list[TrendItem] = []
        with http_client() as http:
            for kw in self.keywords:
                r = http.get(API, params={
                    "query": kw, "tags": "story", "hitsPerPage": self.per_keyword,
                    "numericFilters": f"created_at_i>{since},points>5",
                })
                r.raise_for_status()
                for hit in r.json().get("hits", []):
                    out.append(TrendItem(
                        id=f"hn:{hit['objectID']}",
                        source=self.name,
                        title=hit.get("title") or "",
                        url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit['objectID']}",
                        published_at=datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc),
                        engagement=hit.get("points") or 0,
                        comments=hit.get("num_comments") or 0,
                    ))
        return out
