from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .models import Profile

EXAMPLE_PROFILE = Path(__file__).with_name("profile.example.toml")


def _home() -> Path:
    return Path(os.environ.get("CREATORHUB_HOME") or Path.home() / ".creatorhub")


def _load_dotenv(path: Path) -> None:
    """Tiny .env loader so we don't need python-dotenv. Real env vars win."""
    if not path.is_file():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        value = "" if value.startswith("#") else value.split(" #", 1)[0].strip()
        os.environ.setdefault(key.strip(), value.strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    home: Path
    db_path: Path
    profile_path: Path
    anthropic_api_key: str | None
    youtube_api_key: str | None
    youtube_channel_id: str | None
    digest_hour: int | None
    notion_token: str | None
    notion_database_id: str | None
    ntfy_topic: str | None
    discord_webhook_url: str | None
    desktop_notifications: bool
    scan_interval_minutes: int
    watch_in_server: bool
    model: str

    @classmethod
    def load(cls) -> "Settings":
        _load_dotenv(Path.cwd() / ".env")
        home = _home()
        _load_dotenv(home / ".env")
        env = os.environ.get
        return cls(
            home=home,
            db_path=home / "creatorhub.db",
            profile_path=home / "profile.toml",
            anthropic_api_key=env("ANTHROPIC_API_KEY") or None,
            youtube_api_key=env("YOUTUBE_API_KEY") or None,
            youtube_channel_id=env("YOUTUBE_CHANNEL_ID") or None,
            # Local hour (0-23) to send the daily digest; "off" disables it.
            digest_hour=None if env("CREATORHUB_DIGEST_HOUR", "8").lower() == "off" else int(env("CREATORHUB_DIGEST_HOUR") or 8),
            notion_token=env("NOTION_TOKEN") or None,
            notion_database_id=env("NOTION_DATABASE_ID") or None,
            ntfy_topic=env("NTFY_TOPIC") or None,
            discord_webhook_url=env("DISCORD_WEBHOOK_URL") or None,
            desktop_notifications=env("DESKTOP_NOTIFICATIONS", "1") == "1",
            scan_interval_minutes=int(env("CREATORHUB_SCAN_INTERVAL") or 60),
            watch_in_server=env("CREATORHUB_WATCH_IN_SERVER", "0") == "1",
            model=env("CREATORHUB_MODEL") or "claude-opus-5-5",
        )


def load_profile(settings: Settings) -> Profile:
    path = settings.profile_path if settings.profile_path.is_file() else EXAMPLE_PROFILE
    with path.open("rb") as f:
        return Profile.model_validate(tomllib.load(f))


def init_home(settings: Settings) -> Path:
    """Create ~/.creatorhub with a starter profile. Never overwrites."""
    settings.home.mkdir(parents=True, exist_ok=True)
    if not settings.profile_path.exists():
        settings.profile_path.write_text(EXAMPLE_PROFILE.read_text())
    return settings.profile_path
