"""Application configuration for AI-Job-Alert-Bot."""

from __future__ import annotations

from dataclasses import dataclass
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - fallback for minimal environments
    def load_dotenv() -> bool:
        """Fallback no-op when python-dotenv is unavailable."""

        return False


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated application settings loaded from environment variables."""

    telegram_token: str
    chat_id: str
    log_level: str
    locations: tuple[str, ...]
    keywords: tuple[str, ...]
    resume_path: str | None = None


def _parse_csv(value: str) -> tuple[str, ...]:
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items


def load_settings() -> Settings:
    """Load and validate application settings from the active environment."""

    load_dotenv()

    missing_variables: list[str] = []

    telegram_token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not telegram_token:
        missing_variables.append("TELEGRAM_TOKEN")

    chat_id = os.getenv("CHAT_ID", "").strip()
    if not chat_id:
        missing_variables.append("CHAT_ID")

    log_level = os.getenv("LOG_LEVEL", "").strip().upper()
    if not log_level:
        missing_variables.append("LOG_LEVEL")

    locations_raw = os.getenv("LOCATIONS", "").strip()
    if not locations_raw:
        missing_variables.append("LOCATIONS")

    keywords_raw = os.getenv("KEYWORDS", "").strip()
    if not keywords_raw:
        missing_variables.append("KEYWORDS")

    resume_path = os.getenv("RESUME_PATH", "").strip() or None

    if missing_variables:
        missing = ", ".join(missing_variables)
        raise ValueError(f"Missing required environment variables: {missing}")

    return Settings(
        telegram_token=telegram_token,
        chat_id=chat_id,
        log_level=log_level,
        locations=_parse_csv(locations_raw),
        keywords=_parse_csv(keywords_raw),
        resume_path=resume_path,
    )