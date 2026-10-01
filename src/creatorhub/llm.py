"""Claude-powered judgment: which trends actually matter, and what to make about them."""

from __future__ import annotations

import json
import logging

import anthropic

from .models import ContentIdea, IdeaBatch, Profile, TrendAssessment, TrendAssessmentBatch

log = logging.getLogger(__name__)

SYSTEM = """You are CreatorHub, a sharp content strategist working as a partner to one specific creator.
You know their niches, audience and voice (below). Be concrete and opinionated: a good idea names
the exact hook, format and why this creator is credible on it. Skip generic advice.

Creator profile:
{profile}"""


def _profile_block(profile: Profile) -> str:
    return profile.model_dump_json(include={"name", "bio", "audience", "voice", "platforms", "niches"}, indent=2)


class Brain:
    def __init__(self, model: str, api_key: str | None = None):
        self.client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self.model = model

    def _parse(self, profile: Profile, prompt: str, schema: type, effort: str = "medium"):
        response = self.client.beta.messages.parse(
            model=self.model,
            # If the main model declines, the API retries on a fallback model inside the same call.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            max_tokens=16000,
            output_config={"effort": effort},
            # The system prompt only changes when the profile does, so it caches across scans.
            system=[{"type": "text", "text": SYSTEM.format(profile=_profile_block(profile)),
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_format=schema,
        )
        if response.stop_reason == "refusal":
            log.warning("model declined request: %s", response.stop_details)
            return None
        return response.parsed_output

    def assess_trends(self, profile: Profile, trends: list[dict], allow_adjacent: bool) -> list[TrendAssessment]:
        if not trends:
            return []
        compact = [{"id": t["id"], "source": t["source"], "title": t["title"],
                    "summary": (t.get("summary") or "")[:300], "engagement": t.get("engagement"),
                    "keyword_niche": t.get("matched_niche")} for t in trends]
        prompt = (
            "Here are trending items from this creator's sources. For each, decide:\n"
            "- core: clearly inside one of their niches and worth a piece of content now\n"
            + ("- adjacent: outside their current niches, but a credible new niche/series they could own given "
               "their background and audience (be selective; only flag real openings)\n" if allow_adjacent else "")
            + "- noise: not worth their time\n\n"
            f"Items:\n{json.dumps(compact, indent=1)}"
        )
        batch = self._parse(profile, prompt, TrendAssessmentBatch, effort="low")
        return batch.assessments if batch else []

    def generate_ideas(self, profile: Profile, trends: list[dict], count: int = 3,
                       platform: str | None = None, extra: str | None = None) -> list[ContentIdea]:
        trend_text = "\n".join(
            f"- [{t['id']}] ({t['source']}, niche: {t.get('matched_niche') or '?'}) {t['title']} {t['url']}"
            for t in trends
        ) or "(no live trends supplied; use the creator's niches)"
        prompt = (
            f"Pitch {count} content ideas for this creator"
            + (f", for {platform}" if platform else "")
            + ". Ground them in these live trends where it makes sense, and cite the trend ids you used "
              "in source_trend_ids.\n\n"
            f"Trends:\n{trend_text}"
            + (f"\n\nExtra direction from the creator: {extra}" if extra else "")
        )
        batch = self._parse(profile, prompt, IdeaBatch, effort="medium")
        return batch.ideas if batch else []
