"""The background loop: collect -> score -> (Claude) judge -> alert -> notify."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from datetime import datetime, timezone

from . import notify, service
from .config import Settings, load_profile
from .llm import Brain
from .models import Alert, Profile
from .scoring import score_item
from .sources import build_sources, collect
from .store import Store

log = logging.getLogger(__name__)

# How many top candidates per scan get a Claude judgment (keeps cost predictable).
JUDGE_TOP_N = 25


@dataclass
class ScanResult:
    fetched: int = 0
    new: int = 0
    judged: int = 0
    alerts: list[Alert] = field(default_factory=list)


def scan(settings: Settings, store: Store, profile: Profile | None = None,
         brain: Brain | None = None, send_notifications: bool = True) -> ScanResult:
    profile = profile or load_profile(settings)
    if brain is None and settings.anthropic_api_key:
        brain = Brain(settings.model, settings.anthropic_api_key)

    items = collect(build_sources(profile, settings))
    result = ScanResult(fetched=len(items))
    known = store.known_trend_ids([i.id for i in items])
    result.new = len(items) - len(known)

    perf = service.load_performance(store)
    multipliers = perf.multipliers() if perf else None
    for item in items:
        score_item(item, profile, previous=store.last_engagement(item.id), niche_multipliers=multipliers)

    # Only spend Claude calls on fresh, promising items we haven't judged yet.
    already_alerted = store.alerted_trend_ids()
    candidates = sorted((i for i in items if i.id not in already_alerted), key=lambda i: i.score, reverse=True)
    candidates = candidates[:JUDGE_TOP_N]
    verdicts = {}
    if brain and candidates:
        try:
            verdicts = {a.trend_id: a for a in brain.assess_trends(
                profile, [c.model_dump(mode="json") for c in candidates], profile.alerts.adjacent_niches)}
            result.judged = len(verdicts)
        except Exception as e:
            log.warning("trend assessment failed, falling back to keyword scores: %s", e)

    for item in items:
        v = verdicts.get(item.id)
        if v:
            if v.kind == "noise":
                item.score = round(item.score * 0.3, 1)
            elif v.kind == "core":
                item.score = min(100.0, item.score + 10)
                item.matched_niche = item.matched_niche or v.suggested_niche
            else:  # adjacent: keyword match is weak by definition, so lift it to alert range
                item.score = max(item.score, float(profile.alerts.min_score))
                item.matched_niche = v.suggested_niche
        store.upsert_trend(item, kind=v.kind if v else None, why_now=v.why_now if v else None)

    for item in candidates:
        if len(result.alerts) >= profile.alerts.max_alerts_per_scan:
            break
        v = verdicts.get(item.id)
        if item.score < profile.alerts.min_score or (v and v.kind == "noise"):
            continue
        if v and v.kind == "adjacent":
            alert = Alert(kind="adjacent_niche", title=f"New niche opening: {v.suggested_niche}",
                          body=f"{item.title}\n{v.why_now}", trend_id=item.id, url=item.url)
        else:
            why = v.why_now if v else f"Matched {', '.join(item.matched_keywords) or 'your sources'}"
            alert = Alert(kind="trend", title=f"[{item.matched_niche or 'trend'}] {item.title}"[:140],
                          body=f"Score {item.score:.0f} on {item.source}. {why}", trend_id=item.id, url=item.url)
        alert.id = store.add_alert(alert)
        result.alerts.append(alert)
        if send_notifications:
            notify.send(alert, settings)

    store.set_kv("last_scan", datetime.now(timezone.utc).isoformat())
    log.info("scan: fetched=%d new=%d judged=%d alerts=%d", result.fetched, result.new, result.judged, len(result.alerts))
    return result


def run_forever(settings: Settings) -> None:
    store = Store(settings.db_path)
    log.info("watching every %d min; db=%s", settings.scan_interval_minutes, settings.db_path)
    while True:
        try:
            scan(settings, store)
        except Exception:
            log.exception("scan crashed; will retry next interval")
        try:
            if service.digest_due(settings, store):
                service.send_digest(settings, store)
                log.info("daily digest sent")
        except Exception:
            log.exception("digest failed")
        time.sleep(settings.scan_interval_minutes * 60)
