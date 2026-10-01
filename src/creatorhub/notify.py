"""Fan an alert out to every channel the user configured. Failures are logged, never raised."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess

import httpx

from .config import Settings
from .models import Alert

log = logging.getLogger(__name__)

ICON = {"trend": "📈", "adjacent_niche": "🧭", "idea": "💡"}


def _ps_quote(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _desktop(title: str, body: str) -> None:
    system = platform.system()
    if system == "Darwin":
        # Pass text as argv so quotes in titles can't break the script.
        subprocess.run(["osascript", "-e", "on run argv", "-e",
                        "display notification (item 2 of argv) with title (item 1 of argv)",
                        "-e", "end run", title, body], check=False, timeout=5)
    elif system == "Linux" and shutil.which("notify-send"):
        subprocess.run(["notify-send", title, body], check=False, timeout=5)
    elif system == "Windows":
        ps = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null;"
            "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);"
            "$x=$t.GetElementsByTagName('text');"
            f"$x.Item(0).AppendChild($t.CreateTextNode({_ps_quote(title)})) > $null;"
            f"$x.Item(1).AppendChild($t.CreateTextNode({_ps_quote(body)})) > $null;"
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('CreatorHub').Show("
            "[Windows.UI.Notifications.ToastNotification]::new($t))"
        )
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False, timeout=10)


def send(alert: Alert, settings: Settings) -> None:
    title = f"{ICON.get(alert.kind, '')} CreatorHub: {alert.title}"[:120]
    body = alert.body[:400]
    if settings.desktop_notifications:
        try:
            _desktop(title, body)
        except Exception as e:
            log.debug("desktop notification failed: %s", e)
    with httpx.Client(timeout=10) as http:
        if settings.ntfy_topic:
            try:
                headers = {"Title": title.encode("utf-8").decode("latin-1", "ignore"), "Tags": alert.kind}
                if alert.url:
                    headers["Click"] = alert.url
                http.post(f"https://ntfy.sh/{settings.ntfy_topic}", content=body.encode(), headers=headers)
            except Exception as e:
                log.warning("ntfy failed: %s", e)
        if settings.discord_webhook_url:
            try:
                http.post(settings.discord_webhook_url, json={
                    "content": f"**{title}**\n{body}" + (f"\n{alert.url}" if alert.url else "")
                })
            except Exception as e:
                log.warning("discord failed: %s", e)
