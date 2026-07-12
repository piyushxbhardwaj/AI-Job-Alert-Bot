"""Telegram notification helpers for AI-Job-Alert-Bot."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


def _escape_markdown(value: str) -> str:
    """Escape Telegram Markdown v1 control characters."""

    escaped = value.replace("\\", "\\\\")
    for character in ("_", "*", "[", "]", "(", ")"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped


def _sanitize_url(url: str) -> str:
    """Make a URL safe for Telegram Markdown links."""

    return url.replace("(", "%28").replace(")", "%29")


@dataclass(slots=True)
class TelegramNotifier:
    """Send Telegram messages for new matching jobs."""

    token: str
    chat_id: str
    timeout: float = 10.0
    session: requests.Session | None = None

    @property
    def api_url(self) -> str:
        """Return the Telegram sendMessage endpoint."""

        return f"https://api.telegram.org/bot{self.token}/sendMessage"

    def _post_message(self, message: str, parse_mode: str = "Markdown") -> bool:
        """Send a message to Telegram and return whether it succeeded."""

        session = self.session or requests.Session()
        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            response = session.post(self.api_url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            body = response.json()
            if not body.get("ok", False):
                LOGGER.error("Telegram API rejected message: %s", body)
                return False
            return True
        except (requests.RequestException, ValueError) as exc:
            LOGGER.error("Failed to send Telegram message", exc_info=exc)
            return False

    def send_message(self, message: str) -> bool:
        """Send a Markdown-formatted message."""

        return self._post_message(message, parse_mode="Markdown")

    def send_error(self, error_message: str) -> bool:
        """Send a formatted error notification."""

        message = f"*Error*\n\n{_escape_markdown(error_message)}"
        return self._post_message(message, parse_mode="Markdown")

    def send_priority_alert(
        self,
        company: str,
        role: str,
        location: str,
        source: str,
        apply_url: str,
    ) -> bool:
        """Send a high-priority job alert message."""

        message = "\n".join(
            [
                "🔥 *PRIORITY COMPANY*",
                "",
                f"🏢 *Company:* {_escape_markdown(company)}",
                f"💼 *Role:* {_escape_markdown(role)}",
                f"📍 *Location:* {_escape_markdown(location)}",
                f"🌐 *Source:* {_escape_markdown(source)}",
                f"🔗 *Apply:* [{_escape_markdown('Open posting')}]({_sanitize_url(apply_url)})",
                "⭐ *Priority Match*",
            ]
        )
        return self._post_message(message, parse_mode="Markdown")