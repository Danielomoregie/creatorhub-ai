"""Local web API + static hosting for the React dashboard (`creatorhub dashboard`).

Binds to 127.0.0.1 only: it has no login, so it must not be exposed to a network.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import BaseModel, ValidationError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route
from starlette.concurrency import run_in_threadpool

from . import service, watcher
from .config import Settings, init_home, load_profile
from .models import ContentIdea
from .store import Store

log = logging.getLogger(__name__)

DIST = Path(__file__).resolve().parents[2] / "dashboard" / "dist"
IDEA_STATUSES = {"new", "saved", "made", "dismissed"}


class GenerateBody(BaseModel):
    count: int = 3
    niche: str | None = None
    platform: str | None = None
    direction: str | None = None


class NicheBody(BaseModel):
    name: str
    keywords: list[str]


def create_app(settings: Settings | None = None, store: Store | None = None) -> Starlette:
    settings = settings or Settings.load()
    init_home(settings)
    store = store or Store(settings.db_path)

    async def body(request: Request, model: type[BaseModel]):
        try:
            return model.model_validate(await request.json())
        except (ValidationError, ValueError) as e:
            raise HTTPException(400, f"Invalid request: {e}")

    async def run(fn, *args):
        """Run blocking work off the event loop, turning known errors into friendly HTTP errors."""
        try:
            return await run_in_threadpool(fn, *args)
        except service.NotConfigured as e:
            raise HTTPException(412, str(e))
        except KeyError as e:
            raise HTTPException(404, str(e).strip("'"))
        except Exception as e:  # network / upstream API failures: show the reason in the UI
            log.exception("request failed")
            raise HTTPException(502, f"{type(e).__name__}: {e}")

    # ---- read ----------------------------------------------------------------

    async def summary(_: Request):
        profile = load_profile(settings)
        perf = service.load_performance(store)
        return JSONResponse({
            "name": profile.name,
            "niches": [n.name for n in profile.niches],
            "counts": store.counts(),
            "last_scan": store.get_kv("last_scan"),
            "digest_last_sent": store.get_kv("digest_last_sent"),
            "digest_hour": settings.digest_hour,
            "integrations": {
                "claude": bool(settings.anthropic_api_key),
                "notion": bool(settings.notion_token and settings.notion_database_id),
                "youtube_trends": bool(settings.youtube_api_key),
                "youtube_stats": bool(settings.youtube_api_key and settings.youtube_channel_id),
                "ntfy": bool(settings.ntfy_topic),
                "discord": bool(settings.discord_webhook_url),
            },
            "has_performance": bool(perf and perf.videos_analyzed),
        })

    async def trends(request: Request):
        q = request.query_params
        return JSONResponse(store.top_trends(limit=int(q.get("limit", 30)), hours=int(q.get("hours", 72)),
                                             niche=q.get("niche") or None))

    async def alerts(request: Request):
        unread_only = request.query_params.get("all") != "1"
        return JSONResponse([a.model_dump(mode="json") for a in store.list_alerts(unread_only=unread_only, limit=50)])

    async def read_alerts(request: Request):
        raw = await request.body()
        ids = json.loads(raw).get("ids") if raw else None
        return JSONResponse({"marked": store.mark_alerts_read(ids)})

    async def ideas(request: Request):
        status = request.query_params.get("status")
        return JSONResponse(store.list_ideas(status=status if status in IDEA_STATUSES else None, limit=100))

    async def profile(_: Request):
        return JSONResponse(load_profile(settings).model_dump())

    async def performance(_: Request):
        p = service.load_performance(store)
        return JSONResponse(p.model_dump(mode="json") if p else None)

    async def digest_preview(_: Request):
        d = await run(lambda: service.build_digest(settings, store, generate=False))
        title, text = service.format_digest(d)
        return JSONResponse({**d.model_dump(), "title": title, "text": text})

    # ---- write ---------------------------------------------------------------

    async def scan(_: Request):
        r = await run(lambda: watcher.scan(settings, store, send_notifications=False))
        return JSONResponse({"fetched": r.fetched, "new": r.new, "judged": r.judged,
                             "alerts": [a.model_dump(mode="json") for a in r.alerts]})

    async def generate(request: Request):
        b = await body(request, GenerateBody)
        count = max(1, min(b.count, 10))
        return JSONResponse(await run(service.generate_ideas, settings, store, count, b.niche, b.platform, b.direction))

    async def create_idea(request: Request):
        idea = await body(request, ContentIdea)
        return JSONResponse(service.save_idea(store, idea), status_code=201)

    async def update_idea(request: Request):
        status = (await request.json()).get("status")
        if status not in IDEA_STATUSES:
            raise HTTPException(400, f"status must be one of {sorted(IDEA_STATUSES)}")
        if not store.set_idea_status(int(request.path_params["id"]), status):
            raise HTTPException(404, "idea not found")
        return JSONResponse({"ok": True})

    async def to_notion(request: Request):
        page_id = await run(service.send_idea_to_notion, settings, store, int(request.path_params["id"]))
        return JSONResponse({"page_id": page_id})

    async def add_niche(request: Request):
        b = await body(request, NicheBody)
        if not b.name.strip() or not b.keywords:
            raise HTTPException(400, "A niche needs a name and at least one keyword.")
        if not await run(service.add_niche, settings, b.name.strip(), b.keywords):
            raise HTTPException(409, f"Already tracking '{b.name}'.")
        return JSONResponse({"ok": True}, status_code=201)

    async def refresh_performance(_: Request):
        report = await run(service.refresh_performance, settings, store)
        return JSONResponse(report.model_dump(mode="json"))

    async def send_digest(_: Request):
        d = await run(service.send_digest, settings, store)
        return JSONResponse(d.model_dump())

    # ---- dashboard files -----------------------------------------------------

    async def spa(request: Request):
        if not DIST.is_dir():
            return Response(
                "<h1>Dashboard not built yet</h1><p>Run <code>cd dashboard && npm install && npm run build</code>, "
                "then restart <code>creatorhub dashboard</code>.</p>", media_type="text/html", status_code=503)
        path = (DIST / request.path_params.get("path", "")).resolve()
        if path.is_file() and DIST.resolve() in path.parents:
            return FileResponse(path)
        return FileResponse(DIST / "index.html")

    async def error(_: Request, exc: HTTPException):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    routes = [
        Route("/api/summary", summary),
        Route("/api/trends", trends),
        Route("/api/alerts", alerts),
        Route("/api/alerts/read", read_alerts, methods=["POST"]),
        Route("/api/ideas", ideas),
        Route("/api/ideas", create_idea, methods=["POST"]),
        Route("/api/ideas/generate", generate, methods=["POST"]),
        Route("/api/ideas/{id:int}", update_idea, methods=["PATCH"]),
        Route("/api/ideas/{id:int}/notion", to_notion, methods=["POST"]),
        Route("/api/profile", profile),
        Route("/api/niches", add_niche, methods=["POST"]),
        Route("/api/performance", performance),
        Route("/api/performance/refresh", refresh_performance, methods=["POST"]),
        Route("/api/digest", digest_preview),
        Route("/api/digest/send", send_digest, methods=["POST"]),
        Route("/api/scan", scan, methods=["POST"]),
        Route("/", spa),
        Route("/{path:path}", spa),
    ]
    return Starlette(routes=routes, exception_handlers={HTTPException: error})


def ensure_built() -> None:
    """Build the React dashboard on first run if Node is installed, so one command is enough."""
    import shutil
    import subprocess

    if DIST.is_dir():
        return
    npm = shutil.which("npm")
    if not npm:
        print("Node.js isn't installed, so the dashboard UI can't be built. Get it from https://nodejs.org "
              "(LTS), then run this again. The API still works at /api.")
        return
    print("First run: building the dashboard (takes a minute)...")
    cwd = DIST.parent
    subprocess.run([npm, "install", "--no-audit", "--no-fund"], cwd=cwd, check=True)
    subprocess.run([npm, "run", "build"], cwd=cwd, check=True)


def run_dashboard(port: int = 8765, open_browser: bool = True) -> None:
    import threading
    import webbrowser

    import uvicorn

    ensure_built()
    url = f"http://127.0.0.1:{port}"
    print(f"CreatorHub dashboard: {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
