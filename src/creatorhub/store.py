"""SQLite persistence. WAL mode so the watcher daemon and the MCP server can share one file."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from .models import Alert, ContentIdea, MyVideo, TrendItem

SCHEMA = """
CREATE TABLE IF NOT EXISTS trends (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    summary TEXT,
    published_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    engagement INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    score REAL DEFAULT 0,
    matched_niche TEXT,
    matched_keywords TEXT,
    kind TEXT,
    why_now TEXT
);
CREATE INDEX IF NOT EXISTS trends_score ON trends(score DESC);

-- Engagement snapshots let us measure momentum (growth between scans), not just size.
CREATE TABLE IF NOT EXISTS trend_snapshots (
    trend_id TEXT NOT NULL,
    taken_at TEXT NOT NULL,
    engagement INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    niche TEXT,
    status TEXT NOT NULL DEFAULT 'new',  -- new | saved | made | dismissed
    notion_page_id TEXT,
    data TEXT NOT NULL
);

-- Small key/value bag: last scan time, last digest date, cached performance report...
CREATE TABLE IF NOT EXISTS kv (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- The creator's own uploads, for learning what works for *their* audience.
CREATE TABLE IF NOT EXISTS my_videos (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    published_at TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    tags TEXT,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    trend_id TEXT,
    url TEXT,
    created_at TEXT NOT NULL,
    read INTEGER NOT NULL DEFAULT 0
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path | str):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._conn:
            yield self._conn

    # ---- trends -------------------------------------------------------------

    def known_trend_ids(self, ids: list[str]) -> set[str]:
        if not ids:
            return set()
        q = f"SELECT id FROM trends WHERE id IN ({','.join('?' * len(ids))})"
        return {r["id"] for r in self._conn.execute(q, ids)}

    def last_engagement(self, trend_id: str) -> tuple[int, datetime] | None:
        row = self._conn.execute(
            "SELECT engagement, taken_at FROM trend_snapshots WHERE trend_id=? ORDER BY taken_at DESC LIMIT 1",
            (trend_id,),
        ).fetchone()
        return (row["engagement"], datetime.fromisoformat(row["taken_at"])) if row else None

    def upsert_trend(self, t: TrendItem, kind: str | None = None, why_now: str | None = None) -> None:
        now = _now()
        with self.tx() as c:
            c.execute(
                """INSERT INTO trends (id, source, title, url, summary, published_at, first_seen_at,
                       engagement, comments, score, matched_niche, matched_keywords, kind, why_now)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET
                       engagement=excluded.engagement, comments=excluded.comments, score=excluded.score,
                       matched_niche=COALESCE(excluded.matched_niche, trends.matched_niche),
                       matched_keywords=excluded.matched_keywords,
                       kind=COALESCE(excluded.kind, trends.kind),
                       why_now=COALESCE(excluded.why_now, trends.why_now)""",
                (t.id, t.source, t.title, t.url, t.summary, t.published_at.isoformat(), now,
                 t.engagement, t.comments, t.score, t.matched_niche, json.dumps(t.matched_keywords), kind, why_now),
            )
            c.execute("INSERT INTO trend_snapshots VALUES (?,?,?)", (t.id, now, t.engagement))

    def top_trends(self, limit: int = 20, hours: int = 72, niche: str | None = None) -> list[dict]:
        since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        q = "SELECT * FROM trends WHERE first_seen_at >= ? AND (kind IS NULL OR kind != 'noise')"
        args: list = [since]
        if niche:
            q += " AND matched_niche LIKE ?"
            args.append(f"%{niche}%")
        q += " ORDER BY score DESC LIMIT ?"
        args.append(limit)
        rows = self._conn.execute(q, args).fetchall()
        return [{**dict(r), "matched_keywords": json.loads(r["matched_keywords"] or "[]")} for r in rows]

    def get_trends(self, ids: list[str]) -> list[dict]:
        if not ids:
            return []
        q = f"SELECT * FROM trends WHERE id IN ({','.join('?' * len(ids))})"
        return [dict(r) for r in self._conn.execute(q, ids)]

    # ---- ideas --------------------------------------------------------------

    def add_idea(self, idea: ContentIdea) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO ideas (created_at, niche, data) VALUES (?,?,?)",
                (_now(), idea.niche, idea.model_dump_json()),
            )
            return int(cur.lastrowid)

    def list_ideas(self, status: str | None = None, limit: int = 20) -> list[dict]:
        q, args = "SELECT * FROM ideas", []
        if status:
            q += " WHERE status=?"
            args.append(status)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        out = []
        for r in self._conn.execute(q, args):
            out.append({"id": r["id"], "created_at": r["created_at"], "status": r["status"],
                        "notion_page_id": r["notion_page_id"], **json.loads(r["data"])})
        return out

    def get_idea(self, idea_id: int) -> tuple[ContentIdea, dict] | None:
        r = self._conn.execute("SELECT * FROM ideas WHERE id=?", (idea_id,)).fetchone()
        if not r:
            return None
        return ContentIdea.model_validate_json(r["data"]), dict(r)

    def set_idea_status(self, idea_id: int, status: str, notion_page_id: str | None = None) -> bool:
        with self.tx() as c:
            cur = c.execute(
                "UPDATE ideas SET status=?, notion_page_id=COALESCE(?, notion_page_id) WHERE id=?",
                (status, notion_page_id, idea_id),
            )
            return cur.rowcount > 0

    # ---- alerts -------------------------------------------------------------

    def add_alert(self, a: Alert) -> int:
        with self.tx() as c:
            cur = c.execute(
                "INSERT INTO alerts (kind, title, body, trend_id, url, created_at) VALUES (?,?,?,?,?,?)",
                (a.kind, a.title, a.body, a.trend_id, a.url, a.created_at.isoformat()),
            )
            return int(cur.lastrowid)

    def alerted_trend_ids(self) -> set[str]:
        return {r[0] for r in self._conn.execute("SELECT trend_id FROM alerts WHERE trend_id IS NOT NULL")}

    def list_alerts(self, unread_only: bool = True, limit: int = 20) -> list[Alert]:
        q = "SELECT * FROM alerts" + (" WHERE read=0" if unread_only else "") + " ORDER BY id DESC LIMIT ?"
        return [Alert(**{**dict(r), "read": bool(r["read"])}) for r in self._conn.execute(q, (limit,))]

    def mark_alerts_read(self, ids: list[int] | None = None) -> int:
        with self.tx() as c:
            if ids:
                cur = c.execute(f"UPDATE alerts SET read=1 WHERE id IN ({','.join('?' * len(ids))})", ids)
            else:
                cur = c.execute("UPDATE alerts SET read=1 WHERE read=0")
            return cur.rowcount

    # ---- kv -----------------------------------------------------------------

    def get_kv(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_kv(self, key: str, value: str) -> None:
        with self.tx() as c:
            c.execute("INSERT INTO kv VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    # ---- my videos ----------------------------------------------------------

    def upsert_videos(self, videos: list[MyVideo]) -> None:
        now = _now()
        with self.tx() as c:
            c.executemany(
                """INSERT INTO my_videos VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET title=excluded.title, views=excluded.views,
                       likes=excluded.likes, comments=excluded.comments, tags=excluded.tags,
                       fetched_at=excluded.fetched_at""",
                [(v.id, v.title, v.url, v.published_at.isoformat(), v.views, v.likes, v.comments,
                  json.dumps(v.tags), now) for v in videos],
            )

    def list_videos(self) -> list[MyVideo]:
        rows = self._conn.execute("SELECT * FROM my_videos ORDER BY published_at DESC").fetchall()
        return [MyVideo(id=r["id"], title=r["title"], url=r["url"],
                        published_at=datetime.fromisoformat(r["published_at"]), views=r["views"],
                        likes=r["likes"], comments=r["comments"], tags=json.loads(r["tags"] or "[]"))
                for r in rows]

    def counts(self) -> dict:
        one = lambda q, *a: self._conn.execute(q, a).fetchone()[0]  # noqa: E731
        since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        return {
            "trends_24h": one("SELECT COUNT(*) FROM trends WHERE first_seen_at >= ?", since),
            "unread_alerts": one("SELECT COUNT(*) FROM alerts WHERE read=0"),
            "ideas": one("SELECT COUNT(*) FROM ideas WHERE status != 'dismissed'"),
            "ideas_made": one("SELECT COUNT(*) FROM ideas WHERE status = 'made'"),
        }
