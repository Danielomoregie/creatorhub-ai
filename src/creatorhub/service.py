"""Operations shared by the MCP server, the dashboard API and the CLI."""

from __future__ import annotations

import logging
from datetime import datetime

from . import notify
from .config import Settings, init_home, load_profile
from .llm import Brain
from .models import Alert, ContentIdea, Digest, PerformanceReport
from .notion import Notion
from .store import Store
from .youtube_stats import analyze, fetch_channel_videos

log = logging.getLogger(__name__)


class NotConfigured(Exception):
    """A feature needs an API key or setting the user hasn't added yet."""


def brain(settings: Settings) -> Brain | None:
    return Brain(settings.model, settings.anthropic_api_key) if settings.anthropic_api_key else None


# ---- your channel's performance ------------------------------------------------

def load_performance(store: Store) -> PerformanceReport | None:
    raw = store.get_kv("performance")
    return PerformanceReport.model_validate_json(raw) if raw else None


def refresh_performance(settings: Settings, store: Store) -> PerformanceReport:
    if not (settings.youtube_api_key and settings.youtube_channel_id):
        raise NotConfigured("Add YOUTUBE_API_KEY and YOUTUBE_CHANNEL_ID to ~/.creatorhub/.env to learn from your channel.")
    videos = fetch_channel_videos(settings.youtube_api_key, settings.youtube_channel_id)
    store.upsert_videos(videos)
    report = analyze(videos, load_profile(settings), settings.youtube_channel_id)
    store.set_kv("performance", report.model_dump_json())
    return report


# ---- ideas -------------------------------------------------------------------

def generate_ideas(settings: Settings, store: Store, count: int = 3, niche: str | None = None,
                   platform: str | None = None, direction: str | None = None) -> list[dict]:
    b = brain(settings)
    if b is None:
        raise NotConfigured("Add ANTHROPIC_API_KEY to ~/.creatorhub/.env so CreatorHub can write ideas.")
    trends = store.top_trends(limit=10, hours=96, niche=niche)
    perf = load_performance(store)
    ideas = b.generate_ideas(load_profile(settings), trends, count=count, platform=platform, extra=direction,
                             performance=perf.summary_for_prompt() if perf and perf.videos_analyzed else None)
    return [{"id": store.add_idea(i), "status": "new", **i.model_dump()} for i in ideas]


def send_idea_to_notion(settings: Settings, store: Store, idea_id: int) -> str:
    if not (settings.notion_token and settings.notion_database_id):
        raise NotConfigured("Add NOTION_TOKEN and NOTION_DATABASE_ID to ~/.creatorhub/.env to sync with Notion.")
    found = store.get_idea(idea_id)
    if not found:
        raise KeyError(f"no idea with id {idea_id}")
    idea, _row = found
    trends = store.get_trends(idea.source_trend_ids[:1])
    page_id = Notion(settings.notion_token, settings.notion_database_id).save_idea(
        idea, trends[0]["url"] if trends else None)
    store.set_idea_status(idea_id, "saved", notion_page_id=page_id)
    return page_id


def add_niche(settings: Settings, name: str, keywords: list[str]) -> bool:
    """Append a niche to profile.toml. Returns False if it already exists."""
    path = init_home(settings)
    safe_name = name.replace('"', "'").replace("\\", "/").strip()
    if any(n.name.lower() == safe_name.lower() for n in load_profile(settings).niches):
        return False
    quoted = ", ".join('"' + k.replace('"', "'").replace("\\", "/") + '"' for k in keywords if k.strip())
    block = f'\n[[niches]]\nname = "{safe_name}"\nkeywords = [{quoted}]\n'
    text = path.read_text()
    # [[niches]] entries must come before the [sources] table in TOML.
    idx = text.find("\n[sources]")
    path.write_text(text[:idx] + block + text[idx:] if idx != -1 else text + block)
    load_profile(settings)  # raises if we produced invalid TOML
    return True


# ---- daily digest ------------------------------------------------------------

def build_digest(settings: Settings, store: Store, generate: bool = True) -> Digest:
    trends = store.top_trends(limit=3, hours=24) or store.top_trends(limit=3, hours=72)
    ideas: list[dict] = []
    if generate and settings.anthropic_api_key:
        try:
            ideas = generate_ideas(settings, store, count=3)
        except Exception as e:
            log.warning("digest idea generation failed: %s", e)
    if not ideas:
        ideas = store.list_ideas(status="new", limit=3)
    return Digest(date=datetime.now().date().isoformat(), trends=trends, ideas=ideas)


def format_digest(d: Digest) -> tuple[str, str]:
    lines = ["🔥 Top trends"]
    lines += [f"{i}. {t['title'][:100]} ({t.get('matched_niche') or t['source']})" for i, t in enumerate(d.trends, 1)]
    if not d.trends:
        lines.append("Quiet day. Nothing new cleared your bar.")
    lines.append("\n💡 Ideas for today")
    lines += [f"{i}. {x['title']} [{x.get('format', '')}]" for i, x in enumerate(d.ideas, 1)]
    if not d.ideas:
        lines.append("No ideas yet. Open the dashboard and hit Generate.")
    return f"Your CreatorHub digest for {d.date}", "\n".join(lines)


def digest_due(settings: Settings, store: Store, now: datetime | None = None) -> bool:
    now = now or datetime.now()
    if settings.digest_hour is None or now.hour < settings.digest_hour:
        return False
    return store.get_kv("digest_last_sent") != now.date().isoformat()


def send_digest(settings: Settings, store: Store) -> Digest:
    d = build_digest(settings, store)
    title, body = format_digest(d)
    alert = Alert(kind="digest", title=title, body=body)
    alert.id = store.add_alert(alert)
    notify.send(alert, settings)
    store.set_kv("digest_last_sent", d.date)
    return d


def save_idea(store: Store, idea: ContentIdea) -> dict:
    return {"id": store.add_idea(idea), "status": "new", **idea.model_dump()}
