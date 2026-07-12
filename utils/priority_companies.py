"""Priority company helpers for alerts and dashboards."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_PRIORITY_COMPANIES_PATH = Path("priority_companies.json")


def load_priority_companies(path: str | Path | None = None) -> tuple[str, ...]:
    """Load a list of priority companies from a JSON file if it exists."""

    priority_path = Path(path) if path is not None else DEFAULT_PRIORITY_COMPANIES_PATH
    if not priority_path.exists():
        return tuple()

    try:
        payload = json.loads(priority_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return tuple()

    if isinstance(payload, list):
        return tuple(str(item).strip() for item in payload if str(item).strip())
    return tuple()


def is_priority_company(company: str, priority_companies: tuple[str, ...] | list[str]) -> bool:
    """Return True when the company is present in the configured priority list."""

    normalized_company = company.strip().lower()
    return any(normalized_company == item.strip().lower() for item in priority_companies)