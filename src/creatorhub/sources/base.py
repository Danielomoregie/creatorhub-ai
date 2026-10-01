from __future__ import annotations

from abc import ABC, abstractmethod

import httpx

from ..models import TrendItem

USER_AGENT = "creatorhub-ai/0.1 (personal trend watcher)"


def http_client() -> httpx.Client:
    return httpx.Client(timeout=15, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


class Source(ABC):
    name: str = "source"

    @abstractmethod
    def fetch(self) -> list[TrendItem]: ...
