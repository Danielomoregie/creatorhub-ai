"""CreatorHub MCP server: plug it into Claude Desktop / Claude Code / any MCP client.

Claude gets tools to read your live trends and alerts, pitch ideas grounded in them,
keep an idea backlog, and push ideas to Notion.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Literal

import anyio
import anyio.to_thread

from mcp.server.mcpserver import MCPServer

from . import watcher
from .config import Settings, init_home, load_profile
from .llm import Brain
from .models import ContentIdea
from .notion import Notion
from .store import Store

log = logging.getLogger(__name__)


@lru_cache
def settings() -> Settings:
    return Settings.load()


@lru_cache
def store() -> Store:
    return Store(settings().db_path)


def brain() -> Brain | None:
    s = settings()
    return Brain(s.model, s.anthropic_api_key) if s.anthropic_api_key else None


@asynccontextmanager
async def lifespan(_server: MCPServer):
    """Optionally run the trend watcher inside this process (CREATORHUB_WATCH_IN_SERVER=1).

    The recommended setup is the standalone `creatorhub watch` daemon, which keeps running
    even when your MCP client is closed. Both share the same SQLite file.
    """
    s = settings()
    init_home(s)
    async with anyio.create_task_group() as tg:
        if s.watch_in_server:
            async def loop() -> None:
                while True:
                    try:
                        await anyio.to_thread.run_sync(lambda: watcher.scan(s, store()))
                    except Exception:
                        log.exception("background scan failed")
                    await anyio.sleep(s.scan_interval_minutes * 60)

            tg.start_soon(loop)
        yield {}
        tg.cancel_scope.cancel()


mcp = MCPServer(
    "CreatorHub AI",
    instructions=(
        "CreatorHub is the user's content partner. It watches trends around their niches in the background. "
        "Start with get_alerts to see what popped up, use get_trending for the bigger picture, and pitch ideas "
        "that tie a live trend to the user's niche, audience and voice (see get_profile). Save ideas the user "
        "likes with save_idea, and push them to Notion with send_idea_to_notion when asked."
    ),
    lifespan=lifespan,
)


# ---- reading the world ------------------------------------------------------

@mcp.tool()
def get_profile() -> dict:
    """The creator's profile: bio, audience, voice, platforms, niches and keywords."""
    return load_profile(settings()).model_dump()


@mcp.tool()
def get_alerts(unread_only: bool = True, mark_read: bool = True, limit: int = 20) -> list[dict]:
    """New things the background watcher flagged: hot trends in a niche, and adjacent-niche openings."""
    alerts = store().list_alerts(unread_only=unread_only, limit=limit)
    if mark_read and alerts:
        store().mark_alerts_read([a.id for a in alerts if a.id is not None])
    return [a.model_dump(mode="json") for a in alerts]


@mcp.tool()
def get_trending(niche: str | None = None, hours: int = 72, limit: int = 15) -> list[dict]:
    """Top-scoring trends seen in the last `hours`, optionally filtered to one niche (substring match).

    score is 0-100 (relevance to the creator + momentum + freshness). kind is Claude's verdict:
    core, adjacent (a possible new niche) or null if not yet judged.
    """
    return store().top_trends(limit=limit, hours=hours, niche=niche)


@mcp.tool()
def scan_now() -> dict:
    """Run a trend scan immediately instead of waiting for the background watcher."""
    r = watcher.scan(settings(), store(), send_notifications=False)
    return {"fetched": r.fetched, "new": r.new, "judged": r.judged,
            "alerts": [a.model_dump(mode="json") for a in r.alerts]}


# ---- ideas ------------------------------------------------------------------

@mcp.tool()
def generate_ideas(count: int = 3, niche: str | None = None, platform: str | None = None,
                   direction: str | None = None) -> dict:
    """Pitch content ideas grounded in current trends.

    With ANTHROPIC_API_KEY set, CreatorHub writes and saves the ideas itself. Without it, this
    returns the trend context and you (the assistant) should write the ideas, then call save_idea
    for the ones the user wants to keep.
    """
    trends = store().top_trends(limit=10, hours=96, niche=niche)
    b = brain()
    if b is None:
        return {"mode": "context_only", "profile": get_profile(), "trends": trends,
                "instructions": f"Write {count} ideas" + (f" for {platform}" if platform else "")
                                + (f". Direction: {direction}" if direction else "")}
    ideas = b.generate_ideas(load_profile(settings()), trends, count=count, platform=platform, extra=direction)
    return {"mode": "generated", "ideas": [{"id": store().add_idea(i), **i.model_dump()} for i in ideas]}


@mcp.tool()
def save_idea(title: str, format: str, hook: str, angle: str, outline: list[str], niche: str,
              source_trend_ids: list[str] | None = None) -> dict:
    """Save an idea to the backlog."""
    idea = ContentIdea(title=title, format=format, hook=hook, angle=angle, outline=outline,
                       niche=niche, source_trend_ids=source_trend_ids or [])
    return {"id": store().add_idea(idea), **idea.model_dump()}


@mcp.tool()
def list_ideas(status: Literal["new", "saved", "made", "dismissed"] | None = None, limit: int = 20) -> list[dict]:
    """The idea backlog, newest first."""
    return store().list_ideas(status=status, limit=limit)


@mcp.tool()
def update_idea_status(idea_id: int, status: Literal["new", "saved", "made", "dismissed"]) -> str:
    """Move an idea through the pipeline."""
    return "ok" if store().set_idea_status(idea_id, status) else f"no idea with id {idea_id}"


@mcp.tool()
def send_idea_to_notion(idea_id: int) -> str:
    """Create a page for this idea in the user's Notion content database."""
    s = settings()
    if not (s.notion_token and s.notion_database_id):
        return "Notion isn't configured. Set NOTION_TOKEN and NOTION_DATABASE_ID in ~/.creatorhub/.env."
    found = store().get_idea(idea_id)
    if not found:
        return f"no idea with id {idea_id}"
    idea, _row = found
    trends = store().get_trends(idea.source_trend_ids[:1])
    page_id = Notion(s.notion_token, s.notion_database_id).save_idea(idea, trends[0]["url"] if trends else None)
    store().set_idea_status(idea_id, "saved", notion_page_id=page_id)
    return f"Saved to Notion (page {page_id})."


# ---- profile ------------------------------------------------------------------

@mcp.tool()
def add_niche(name: str, keywords: list[str]) -> str:
    """Start tracking a new niche (e.g. after an adjacent-niche alert the user wants to pursue)."""
    s = settings()
    path = init_home(s)
    if any(n.name.lower() == name.lower() for n in load_profile(s).niches):
        return f"Already tracking '{name}'."
    quoted = ", ".join('"' + k.replace('"', "'") + '"' for k in keywords)
    block = f'\n[[niches]]\nname = "{name.replace(chr(34), chr(39))}"\nkeywords = [{quoted}]\n'
    text = path.read_text()
    # [[niches]] must come before the [sources] table in TOML, so insert there.
    idx = text.find("\n[sources]")
    path.write_text(text[:idx] + block + text[idx:] if idx != -1 else text + block)
    load_profile(s)  # validate
    return f"Now tracking '{name}' ({len(keywords)} keywords). The next scan will include it."


@mcp.resource("creatorhub://profile", mime_type="application/json")
def profile_resource() -> str:
    return load_profile(settings()).model_dump_json(indent=2)


@mcp.prompt()
def weekly_plan(platform: str = "all my platforms") -> str:
    """Plan next week's content from what's trending."""
    return (
        f"Check my CreatorHub alerts and trending topics, then build next week's content plan for {platform}. "
        "Mix core-niche pieces with at most one experiment from an adjacent niche. For each piece give the "
        "day, format, hook and the trend it rides. Then ask which ones to save."
    )


def run(transport: Literal["stdio", "streamable-http"] = "stdio") -> None:
    mcp.run(transport)
