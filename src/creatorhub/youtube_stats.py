"""Learn from the creator's own channel: which niches over- or under-perform for *their* audience.

Uses only public data (YouTube Data API key + channel id, no OAuth). The result nudges trend
scores per niche and is given to Claude when writing ideas.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from .models import MyVideo, NichePerformance, PerformanceReport, Profile
from .scoring import keyword_hits
from .sources.base import http_client

API = "https://www.googleapis.com/youtube/v3"

# A niche's multiplier is bounded so one viral video can't take over the feed.
MIN_MULT, MAX_MULT = 0.8, 1.25
MIN_VIDEOS_PER_NICHE = 2


def fetch_channel_videos(api_key: str, channel_id: str, max_videos: int = 50) -> list[MyVideo]:
    with http_client() as http:
        r = http.get(f"{API}/channels", params={"key": api_key, "id": channel_id, "part": "contentDetails"})
        r.raise_for_status()
        items = r.json().get("items", [])
        if not items:
            raise ValueError(f"No YouTube channel with id {channel_id!r} (it should start with 'UC')")
        uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

        ids: list[str] = []
        page = None
        while len(ids) < max_videos:
            r = http.get(f"{API}/playlistItems", params={
                "key": api_key, "playlistId": uploads, "part": "contentDetails",
                "maxResults": min(50, max_videos - len(ids)), **({"pageToken": page} if page else {}),
            })
            r.raise_for_status()
            data = r.json()
            ids += [i["contentDetails"]["videoId"] for i in data.get("items", [])]
            page = data.get("nextPageToken")
            if not page:
                break

        videos: list[MyVideo] = []
        for chunk in (ids[i:i + 50] for i in range(0, len(ids), 50)):
            r = http.get(f"{API}/videos", params={"key": api_key, "id": ",".join(chunk), "part": "snippet,statistics"})
            r.raise_for_status()
            for v in r.json().get("items", []):
                sn, st = v["snippet"], v.get("statistics", {})
                videos.append(MyVideo(
                    id=v["id"], title=sn.get("title", ""), url=f"https://www.youtube.com/watch?v={v['id']}",
                    published_at=datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00")),
                    views=int(st.get("viewCount", 0)), likes=int(st.get("likeCount", 0)),
                    comments=int(st.get("commentCount", 0)), tags=sn.get("tags", [])[:15],
                ))
        return videos


def analyze(videos: list[MyVideo], profile: Profile, channel_id: str = "",
            now: datetime | None = None) -> PerformanceReport:
    now = now or datetime.now(timezone.utc)
    # Videos younger than 3 days haven't settled yet; comparing them would punish new uploads.
    settled = [v for v in videos if now - v.published_at >= timedelta(days=3)]
    if not settled:
        return PerformanceReport(channel_id=channel_id, videos_analyzed=0, median_views=0)

    median = max(1, int(statistics.median(v.views for v in settled)))
    by_niche: dict[str, list[float]] = {}
    for v in settled:
        text = f"{v.title} {' '.join(v.tags)}"
        best, best_score = None, 0.0
        for niche in profile.niches:
            s, _ = keyword_hits(text, niche.keywords + [niche.name])
            if s > best_score:
                best, best_score = niche.name, s
        if best:
            by_niche.setdefault(best, []).append(v.views / median)

    niches = []
    for name, ratios in sorted(by_niche.items()):
        avg = sum(ratios) / len(ratios)
        # sqrt dampens extremes; too few videos = no opinion yet.
        mult = min(MAX_MULT, max(MIN_MULT, avg ** 0.5)) if len(ratios) >= MIN_VIDEOS_PER_NICHE else 1.0
        niches.append(NichePerformance(niche=name, videos=len(ratios), avg_ratio=round(avg, 2),
                                       multiplier=round(mult, 2)))

    ranked = sorted(settled, key=lambda v: v.views, reverse=True)
    return PerformanceReport(channel_id=channel_id, videos_analyzed=len(settled), median_views=median,
                             niches=niches, top=ranked[:5], bottom=ranked[5:][-3:])
