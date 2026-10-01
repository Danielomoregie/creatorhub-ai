"""Push an idea into a Notion database as a page (the original CreatorHub's killer feature).

The database needs a title property; other properties are filled only if they exist:
  Status (select), Niche (select), Format (select), Source (url)
"""

from __future__ import annotations

import os

import httpx

from .models import ContentIdea

API = "https://api.notion.com/v1"


def _text(s: str) -> list[dict]:
    return [{"type": "text", "text": {"content": s[:2000]}}]


class Notion:
    def __init__(self, token: str, database_id: str):
        self.database_id = database_id
        self.http = httpx.Client(timeout=20, headers={
            "Authorization": f"Bearer {token}",
            "Notion-Version": os.environ.get("NOTION_VERSION", "2022-06-28"),
            "Content-Type": "application/json",
        })

    def _schema(self) -> dict:
        r = self.http.get(f"{API}/databases/{self.database_id}")
        r.raise_for_status()
        return r.json()["properties"]

    def save_idea(self, idea: ContentIdea, source_url: str | None = None) -> str:
        schema = self._schema()
        title_prop = next(name for name, p in schema.items() if p["type"] == "title")
        props: dict = {title_prop: {"title": _text(idea.title)}}
        for name, value in (("Status", "Idea"), ("Niche", idea.niche), ("Format", idea.format)):
            if schema.get(name, {}).get("type") == "select":
                props[name] = {"select": {"name": value[:100].replace(",", " ")}}
        if source_url and schema.get("Source", {}).get("type") == "url":
            props["Source"] = {"url": source_url}

        children = [
            {"object": "block", "type": "callout", "callout": {"rich_text": _text(f"Hook: {idea.hook}"), "icon": {"emoji": "🎣"}}},
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": _text(idea.angle)}},
            {"object": "block", "type": "heading_3", "heading_3": {"rich_text": _text("Outline")}},
            *[{"object": "block", "type": "numbered_list_item", "numbered_list_item": {"rich_text": _text(b)}}
              for b in idea.outline],
        ]
        r = self.http.post(f"{API}/pages", json={
            "parent": {"database_id": self.database_id}, "properties": props, "children": children,
        })
        r.raise_for_status()
        return r.json()["id"]
