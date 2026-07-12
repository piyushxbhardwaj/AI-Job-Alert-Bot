"""Job filtering helpers for AI-Job-Alert-Bot."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable


DEFAULT_ALLOWED_ROLES: tuple[str, ...] = (
    "Software Engineer",
    "Software Developer",
    "Backend Engineer",
    "Backend Developer",
    "Full Stack Engineer",
    "Full Stack Developer",
    "Python Developer",
    "AI Engineer",
    "Machine Learning Engineer",
    "ML Engineer",
    "Data Engineer",
    "AI Research Engineer",
    "GenAI Engineer",
    "LLM Engineer",
    "Software Engineer Intern",
    "AI Intern",
    "Machine Learning Intern",
    "Entry Level",
    "New Graduate",
    "Fresher",
)

DEFAULT_REJECTED_TERMS: tuple[str, ...] = (
    "Sales",
    "Marketing",
    "HR",
    "Finance",
    "Customer Support",
    "Recruiter",
    "Business Development",
    "Designer",
    "Manual QA",
)


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _compile_pattern(phrases: Iterable[str]) -> re.Pattern[str] | None:
    escaped = [re.escape(phrase.lower()) for phrase in phrases if phrase.strip()]
    if not escaped:
        return None
    return re.compile(r"(?:^|\b)(" + "|".join(escaped) + r")(?:\b|$)", re.IGNORECASE)


@dataclass(slots=True)
class JobFilter:
    """Allowlist/denylist matcher for job titles and descriptions."""

    allowed_roles: tuple[str, ...] = DEFAULT_ALLOWED_ROLES
    rejected_terms: tuple[str, ...] = DEFAULT_REJECTED_TERMS
    _allowed_pattern: re.Pattern[str] | None = field(init=False, repr=False)
    _rejected_pattern: re.Pattern[str] | None = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_allowed_pattern", _compile_pattern(self.allowed_roles))
        object.__setattr__(self, "_rejected_pattern", _compile_pattern(self.rejected_terms))

    def matches_allowed_role(self, text: str | None) -> bool:
        """Return True when the text matches an allowed role phrase."""

        normalized = _normalize_text(text)
        if not normalized or self._allowed_pattern is None:
            return False
        return self._allowed_pattern.search(normalized) is not None

    def matches_rejected_term(self, text: str | None) -> bool:
        """Return True when the text contains a rejected phrase."""

        normalized = _normalize_text(text)
        if not normalized or self._rejected_pattern is None:
            return False
        return self._rejected_pattern.search(normalized) is not None

    def should_keep(self, title: str, company: str = "", description: str = "", location: str = "") -> bool:
        """Return True when a job matches the allowlist and not the denylist."""

        combined_text = " ".join(part for part in [title, company, description, location] if part)
        if self.matches_rejected_term(combined_text):
            return False
        return self.matches_allowed_role(combined_text)


def is_allowed_role(text: str, allowed_roles: Iterable[str] = DEFAULT_ALLOWED_ROLES) -> bool:
    """Convenience wrapper for a one-off allowlist check."""

    return JobFilter(allowed_roles=tuple(allowed_roles)).matches_allowed_role(text)


def is_rejected_job(text: str, rejected_terms: Iterable[str] = DEFAULT_REJECTED_TERMS) -> bool:
    """Convenience wrapper for a one-off denylist check."""

    return JobFilter(rejected_terms=tuple(rejected_terms)).matches_rejected_term(text)
