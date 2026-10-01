from __future__ import annotations

import calendar
import hashlib
from datetime import datetime, timezone

import feedparser

from ..models import TrendItem
from .base import Source, http_client


class RssSource(Source):
    """Any RSS/Atom feed: newsletters, blogs, Google News queries, hnrss, YouTube channel feeds..."""

    name = "rss"

    def __init__(self, feeds: list[str]):
        self.feeds = feeds

    def fetch(self) -> list[TrendItem]:
        out: list[TrendItem] = []
        with http_client() as http:
            for feed_url in self.feeds:
                r = http.get(feed_url)
                if r.status_code != 200:
                    continue
                feed = feedparser.parse(r.content)
                for e in feed.entries[:30]:
                    link = e.get("link") or feed_url
                    ts = e.get("published_parsed") or e.get("updated_parsed")
                    published = datetime.fromtimestamp(calendar.timegm(ts), tz=timezone.utc) if ts else datetime.now(timezone.utc)
                    out.append(TrendItem(
                        id="rss:" + hashlib.sha1(link.encode()).hexdigest()[:16],
                        source=self.name,
                        title=e.get("title", ""),
                        url=link,
                        summary=(e.get("summary") or "")[:500],
                        published_at=published,
                        tags=[feed.feed.get("title", "")] if feed.feed.get("title") else [],
                    ))
        return out
