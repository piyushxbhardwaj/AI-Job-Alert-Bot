"""Telegram notification helpers for AI-Job-Alert-Bot."""

from __future__ import annotations

from dataclasses import dataclass
import html
import logging
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)


def _escape_html(value: str) -> str:
    """Escape text for Telegram HTML formatting."""
    return html.escape(str(value), quote=True)


@dataclass(slots=True)
class TelegramNotifier:
    """Send Telegram messages for new matching jobs."""

    token: str
    chat_id: str
    timeout: float = 10.0
    session: requests.Session | None = None

    @property
    def api_url(self) -> str:
        """Return Telegram sendMessage endpoint."""
        return f"https://api.telegram.org/bot{self.token}/sendMessage"

    def _post_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """Send a message to Telegram."""

        session = self.session or requests.Session()

        payload: dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }

        try:
            response = session.post(
                self.api_url,
                json=payload,
                timeout=self.timeout,
            )

            body = response.json()

            if not body.get("ok", False):
                LOGGER.error("Telegram API Error: %s", body)
                return False

            return True

        except Exception as exc:
            try:
                LOGGER.error(
                    "Telegram Error: %s\nResponse: %s",
                    exc,
                    response.text,
                )
            except Exception:
                LOGGER.exception("Telegram Error")

            return False

    def send_message(self, message: str) -> bool:
        """Send an already-formatted HTML message."""
        return self._post_message(message)

    def send_error(self, error_message: str) -> bool:
        """Send an error notification."""

        message = (
            "<b>❌ Error</b>\n\n"
            f"{_escape_html(error_message)}"
        )

        return self._post_message(message)

    def send_priority_alert(
        self,
        company: str,
        role: str,
        location: str,
        source: str,
        apply_url: str,
    ) -> bool:
        """Send a priority job alert."""

        message = (
            "🔥 <b>PRIORITY COMPANY</b>\n\n"
            f"🏢 <b>Company:</b> {_escape_html(company)}\n"
            f"💼 <b>Role:</b> {_escape_html(role)}\n"
            f"📍 <b>Location:</b> {_escape_html(location)}\n"
            f"🌐 <b>Source:</b> {_escape_html(source)}\n"
            f'🔗 <a href="{apply_url}">Apply Here</a>\n\n'
            "⭐ <b>Priority Match</b>"
        )

        return self._post_message(message)

    def send_job(
        self,
        company: str,
        role: str,
        location: str,
        source: str,
        apply_url: str,
    ) -> bool:
        """Send a normal job notification."""

        message = (
            "🚀 <b>New Job Found</b>\n\n"
            f"🏢 <b>Company:</b> {_escape_html(company)}\n"
            f"💼 <b>Role:</b> {_escape_html(role)}\n"
            f"📍 <b>Location:</b> {_escape_html(location)}\n"
            f"🌐 <b>Source:</b> {_escape_html(source)}\n"
            f'🔗 <a href="{apply_url}">Apply Here</a>'
        )

        return self._post_message(message)
