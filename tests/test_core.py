from datetime import datetime, timedelta, timezone

from creatorhub.models import Alert, ContentIdea, Niche, Profile, TrendAssessment, TrendItem
from creatorhub.scoring import keyword_hits, score_item
from creatorhub.store import Store
from creatorhub import watcher

NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)

PROFILE = Profile(
    name="Test",
    niches=[Niche(name="Tech careers", keywords=["swe intern", "leetcode"]),
            Niche(name="Space", keywords=["nasa", "artemis"])],
)


def item(title: str, hours_old: float = 2, engagement: int = 100, source: str = "reddit", id: str = "reddit:1"):
    return TrendItem(id=id, source=source, title=title, url="https://x", published_at=NOW - timedelta(hours=hours_old),
                     engagement=engagement)


def test_keyword_hits_phrase_and_loose():
    s, hits = keyword_hits("How I got my SWE intern offer", ["swe intern", "leetcode"])
    assert hits == ["swe intern"] and s == 1.0
    s, hits = keyword_hits("intern at a big SWE shop", ["swe intern"])
    assert hits == ["swe intern"] and s == 0.6
    assert keyword_hits("nasaesque", ["nasa"])[1] == []


def test_relevant_hot_item_outscores_irrelevant_one():
    hot = score_item(item("NASA Artemis II crew update", engagement=800), PROFILE, now=NOW)
    meh = score_item(item("My cat learned to sit", engagement=800), PROFILE, now=NOW)
    assert hot.matched_niche == "Space"
    assert hot.score > meh.score + 30


def test_momentum_rewards_growth_between_scans():
    flat = score_item(item("leetcode grind", hours_old=40, engagement=200), PROFILE,
                      previous=(200, NOW - timedelta(hours=1)), now=NOW)
    rising = score_item(item("leetcode grind", hours_old=40, engagement=200), PROFILE,
                        previous=(20, NOW - timedelta(hours=1)), now=NOW)
    assert rising.score > flat.score


def test_store_roundtrip(tmp_path):
    st = Store(tmp_path / "t.db")
    t = score_item(item("leetcode tips"), PROFILE, now=NOW)
    st.upsert_trend(t, kind="core", why_now="because")
    assert st.known_trend_ids(["reddit:1", "reddit:2"]) == {"reddit:1"}
    assert st.last_engagement("reddit:1")[0] == 100

    idea_id = st.add_idea(ContentIdea(title="T", format="TikTok", hook="h", angle="a", outline=["1"], niche="Space"))
    assert st.list_ideas()[0]["title"] == "T"
    assert st.set_idea_status(idea_id, "made")
    assert st.list_ideas(status="made")[0]["id"] == idea_id

    st.add_alert(Alert(kind="trend", title="x", body="y", trend_id="reddit:1"))
    assert len(st.list_alerts()) == 1
    assert st.mark_alerts_read() == 1
    assert st.list_alerts() == []


class FakeBrain:
    def assess_trends(self, profile, trends, allow_adjacent):
        return [TrendAssessment(trend_id=t["id"], relevant=True,
                                kind="adjacent" if "robot" in t["title"] else "noise" if "cat" in t["title"] else "core",
                                suggested_niche="Robotics" if "robot" in t["title"] else "Space", why_now="now")
                for t in trends]


def test_scan_alerts_core_and_adjacent_but_not_noise(tmp_path, monkeypatch):
    items = [item("NASA Artemis launch date moved", id="r:1", engagement=900, hours_old=1),
             item("Humanoid robot kits for students", id="r:2", engagement=900, hours_old=1),
             item("cat video", id="r:3", engagement=5000, hours_old=1)]
    monkeypatch.setattr(watcher, "collect", lambda _sources: [i.model_copy() for i in items])
    monkeypatch.setattr(watcher, "build_sources", lambda *_: [])
    from creatorhub.config import Settings
    settings = Settings.load()
    st = Store(tmp_path / "t.db")

    r = watcher.scan(settings, st, profile=PROFILE, brain=FakeBrain(), send_notifications=False)
    kinds = {a.trend_id: a.kind for a in r.alerts}
    assert kinds == {"r:1": "trend", "r:2": "adjacent_niche"}

    # Second scan must not re-alert the same trends.
    r2 = watcher.scan(settings, st, profile=PROFILE, brain=FakeBrain(), send_notifications=False)
    assert r2.alerts == []
