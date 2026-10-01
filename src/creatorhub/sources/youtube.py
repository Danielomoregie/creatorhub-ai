from __future__ import annotations

from datetime import datetime, timedelta, timezone

from ..models import TrendItem
from .base import Source, http_client

API = "https://www.googleapis.com/youtube/v3"


class YouTubeSource(Source):
    """Most-viewed recent uploads for each keyword (YouTube Data API v3; needs YOUTUBE_API_KEY).

    Quota note: each search costs 100 units of the free 10k/day, so keep keywords focused
    or raise CREATORHUB_SCAN_INTERVAL.
    """

    name = "youtube"

    def __init__(self, api_key: str, keywords: list[str], region: str = "US", days: int = 3):
        self.api_key = api_key
        self.keywords = keywords
        self.region = region
        self.days = days

    def fetch(self) -> list[TrendItem]:
        after = (datetime.now(timezone.utc) - timedelta(days=self.days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        out: list[TrendItem] = []
        with http_client() as http:
            video_ids: list[str] = []
            for kw in self.keywords:
                r = http.get(f"{API}/search", params={
                    "key": self.api_key, "q": kw, "part": "id", "type": "video", "order": "viewCount",
                    "publishedAfter": after, "regionCode": self.region, "maxResults": 5,
                })
                r.raise_for_status()
                video_ids += [i["id"]["videoId"] for i in r.json().get("items", [])]
            for chunk in (video_ids[i:i + 50] for i in range(0, len(video_ids), 50)):
                r = http.get(f"{API}/videos", params={
                    "key": self.api_key, "id": ",".join(chunk), "part": "snippet,statistics",
                })
                r.raise_for_status()
                for v in r.json().get("items", []):
                    sn, st = v["snippet"], v.get("statistics", {})
                    out.append(TrendItem(
                        id=f"yt:{v['id']}",
                        source=self.name,
                        title=sn.get("title", ""),
                        url=f"https://www.youtube.com/watch?v={v['id']}",
                        summary=(sn.get("description") or "")[:500],
                        published_at=datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00")),
                        engagement=int(st.get("viewCount", 0)),
                        comments=int(st.get("commentCount", 0)),
                        tags=[sn.get("channelTitle", "")],
                    ))
        return out
