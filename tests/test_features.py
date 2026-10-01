from datetime import datetime, timedelta, timezone

import pytest
from starlette.testclient import TestClient

from creatorhub import service
from creatorhub.api import create_app
from creatorhub.config import Settings
from creatorhub.models import Alert, ContentIdea, MyVideo, Niche, Profile, TrendItem
from creatorhub.scoring import score_item
from creatorhub.store import Store
from creatorhub.youtube_stats import MAX_MULT, analyze

NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
PROFILE = Profile(niches=[Niche(name="Tech careers", keywords=["internship", "leetcode"]),
                          Niche(name="Space", keywords=["nasa"])])


@pytest.fixture
def settings(tmp_path, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "NOTION_TOKEN", "NOTION_DATABASE_ID", "YOUTUBE_API_KEY", "YOUTUBE_CHANNEL_ID",
              "NTFY_TOPIC", "DISCORD_WEBHOOK_URL"):
        monkeypatch.setenv(k, "")
    monkeypatch.setenv("CREATORHUB_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DESKTOP_NOTIFICATIONS", "0")
    monkeypatch.setenv("CREATORHUB_DIGEST_HOUR", "8")
    return Settings.load()


def video(i, title, views, days_old=10):
    return MyVideo(id=str(i), title=title, url="u", published_at=NOW - timedelta(days=days_old), views=views)


def test_analyze_boosts_niches_that_outperform():
    vids = [video(1, "My NASA trip", 1000), video(2, "nasa tour", 1200),
            video(3, "leetcode day 1", 100), video(4, "leetcode day 2", 120),
            video(5, "vlog", 300), video(6, "brand new nasa video", 50, days_old=1)]
    report = analyze(vids, PROFILE, now=NOW)
    assert report.videos_analyzed == 5  # the 1-day-old upload is excluded
    mult = report.multipliers()
    assert mult["Space"] > 1 and mult["Tech careers"] < 1
    assert max(mult.values()) <= MAX_MULT
    assert report.top[0].title == "nasa tour"


def test_niche_multiplier_changes_trend_score():
    t = lambda: TrendItem(id="x", source="reddit", title="NASA news", url="u", published_at=NOW, engagement=10)  # noqa: E731
    base = score_item(t(), PROFILE, now=NOW).score
    boosted = score_item(t(), PROFILE, now=NOW, niche_multipliers={"Space": 1.25}).score
    assert boosted > base


def test_digest_due_once_per_day_after_hour(settings, tmp_path):
    store = Store(tmp_path / "d.db")
    assert not service.digest_due(settings, store, now=datetime(2026, 10, 1, 7, 59))
    assert service.digest_due(settings, store, now=datetime(2026, 10, 1, 8, 5))
    store.set_kv("digest_last_sent", "2026-10-01")
    assert not service.digest_due(settings, store, now=datetime(2026, 10, 1, 20))
    assert service.digest_due(settings, store, now=datetime(2026, 10, 2, 9))


def test_send_digest_uses_backlog_without_claude(settings, tmp_path):
    store = Store(tmp_path / "d.db")
    store.add_idea(ContentIdea(title="Idea A", format="TikTok", hook="h", angle="a", outline=["1"], niche="Space"))
    d = service.send_digest(settings, store)
    title, body = service.format_digest(d)
    assert "Idea A" in body and "Quiet day" in body
    assert store.list_alerts()[0].kind == "digest"
    assert not service.digest_due(settings, store)


def test_add_niche_keeps_profile_valid(settings):
    assert service.add_niche(settings, 'Robotics "club"', ["humanoid robot"])
    assert not service.add_niche(settings, 'robotics "club"', ["x"])
    from creatorhub.config import load_profile
    assert "Robotics 'club'" in [n.name for n in load_profile(settings).niches]


def test_api_end_to_end(settings, tmp_path):
    store = Store(tmp_path / "api.db")
    client = TestClient(create_app(settings, store))

    s = client.get("/api/summary").json()
    assert s["integrations"]["claude"] is False and s["counts"]["ideas"] == 0

    r = client.post("/api/ideas", json={"title": "T", "format": "YouTube", "hook": "h", "angle": "a",
                                        "outline": ["1"], "niche": "Space"})
    assert r.status_code == 201
    idea_id = r.json()["id"]
    assert client.patch(f"/api/ideas/{idea_id}", json={"status": "made"}).status_code == 200
    assert client.patch(f"/api/ideas/{idea_id}", json={"status": "bogus"}).status_code == 400
    assert client.get("/api/ideas?status=made").json()[0]["id"] == idea_id

    # Features that need keys explain what to add instead of crashing.
    r = client.post("/api/ideas/generate", json={"count": 3})
    assert r.status_code == 412 and "ANTHROPIC_API_KEY" in r.json()["error"]
    assert client.post(f"/api/ideas/{idea_id}/notion").status_code == 412
    assert client.post("/api/performance/refresh").status_code == 412
    assert client.post("/api/ideas/999/notion").status_code == 412  # config is checked first

    store.add_alert(Alert(kind="trend", title="t", body="b"))
    assert len(client.get("/api/alerts").json()) == 1
    assert client.post("/api/alerts/read").json()["marked"] == 1

    assert client.post("/api/niches", json={"name": "Robotics", "keywords": ["robot"]}).status_code == 201
    assert client.post("/api/niches", json={"name": "Robotics", "keywords": ["robot"]}).status_code == 409
    assert "Robotics" in client.get("/api/summary").json()["niches"]
    assert client.get("/api/digest").json()["title"].startswith("Your CreatorHub digest")
