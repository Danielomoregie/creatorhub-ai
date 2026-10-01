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

from . import service, watcher
from .config import Settings, init_home, load_profile
from .models import ContentIdea
from .store import Store

log = logging.getLogger(__name__)


@lru_cache
def settings() -> Settings:
    return Settings.load()


@lru_cache
def store() -> Store:
    return Store(settings().db_path)


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
    """Pitch content ideas grounded in current trends and in what has worked on the creator's channel.

    With ANTHROPIC_API_KEY set, CreatorHub writes and saves the ideas itself. Without it, this
    returns the context and you (the assistant) should write the ideas, then call save_idea
    for the ones the user wants to keep.
    """
    try:
        return {"mode": "generated",
                "ideas": service.generate_ideas(settings(), store(), count, niche, platform, direction)}
    except service.NotConfigured:
        perf = service.load_performance(store())
        return {"mode": "context_only", "profile": get_profile(),
                "trends": store().top_trends(limit=10, hours=96, niche=niche),
                "my_performance": perf.summary_for_prompt() if perf else None,
                "instructions": f"Write {count} ideas" + (f" for {platform}" if platform else "")
                                + (f". Direction: {direction}" if direction else "")}


@mcp.tool()
def save_idea(title: str, format: str, hook: str, angle: str, outline: list[str], niche: str,
              source_trend_ids: list[str] | None = None) -> dict:
    """Save an idea to the backlog."""
    return service.save_idea(store(), ContentIdea(title=title, format=format, hook=hook, angle=angle,
                                                  outline=outline, niche=niche,
                                                  source_trend_ids=source_trend_ids or []))


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
    try:
        return f"Saved to Notion (page {service.send_idea_to_notion(settings(), store(), idea_id)})."
    except (service.NotConfigured, KeyError) as e:
        return str(e)


# ---- digest & performance ------------------------------------------------------

@mcp.tool()
def get_digest() -> dict:
    """Today's digest: top 3 trends and 3 ideas (from the backlog; does not spend API calls)."""
    return service.build_digest(settings(), store(), generate=False).model_dump()


@mcp.tool()
def get_my_performance(refresh: bool = False) -> dict:
    """How the creator's own YouTube videos perform per niche (vs channel median), plus best and worst videos."""
    try:
        report = service.refresh_performance(settings(), store()) if refresh else service.load_performance(store())
    except service.NotConfigured as e:
        return {"error": str(e)}
    return report.model_dump(mode="json") if report else {"error": "No stats yet. Call again with refresh=true."}


# ---- profile ------------------------------------------------------------------

@mcp.tool()
def add_niche(name: str, keywords: list[str]) -> str:
    """Start tracking a new niche (e.g. after an adjacent-niche alert the user wants to pursue)."""
    if not service.add_niche(settings(), name, keywords):
        return f"Already tracking '{name}'."
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
