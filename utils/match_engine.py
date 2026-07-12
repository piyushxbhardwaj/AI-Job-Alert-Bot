"""Job matching and scoring helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable


SKILL_KEYWORDS: tuple[str, ...] = (
    "python",
    "fastapi",
    "django",
    "flask",
    "sql",
    "postgres",
    "docker",
    "kubernetes",
    "aws",
    "redis",
    "celery",
    "pytorch",
    "tensorflow",
    "machine learning",
    "llm",
    "ai",
    "rag",
    "nlp",
    "vector",
    "api",
    "backend",
    "full stack",
    "data engineering",
)


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def load_resume_text(resume_path: str | None) -> str:
    """Load resume text from a file path if one is configured."""

    if not resume_path:
        return ""

    path = Path(resume_path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


@dataclass(slots=True)
class MatchResult:
    """Structured scoring output for a job posting."""

    match_score: int
    reasons: tuple[str, ...]
    missing_skills: tuple[str, ...]
    resume_match_score: int | None = None


def score_job(
    *,
    title: str,
    company: str,
    description: str = "",
    location: str = "",
    keywords: Iterable[str] = (),
) -> MatchResult:
    """Score a job against the configured keywords and common role signals."""

    text = _normalize_text(" ".join([title, company, description, location, " ".join(keywords)]))
    reasons: list[str] = []
    score = 0

    role_signals = (
        ("python", 16),
        ("backend", 14),
        ("full stack", 12),
        ("machine learning", 18),
        ("ml engineer", 18),
        ("ai engineer", 20),
        ("data engineer", 14),
        ("llm", 18),
        ("genai", 18),
        ("remote", 8),
        ("intern", 10),
        ("entry level", 10),
        ("new graduate", 10),
        ("fresher", 10),
    )

    for phrase, weight in role_signals:
        if phrase in text:
            score += weight
            reasons.append(phrase.title())

    keyword_hits = 0
    for keyword in keywords:
        normalized_keyword = _normalize_text(keyword)
        if normalized_keyword and normalized_keyword in text:
            keyword_hits += 1
            reasons.append(keyword)

    score += min(keyword_hits * 10, 40)
    score = min(score, 100)
    return MatchResult(match_score=score, reasons=tuple(dict.fromkeys(reasons)), missing_skills=())


def score_resume_match(
    *,
    job_description: str,
    resume_text: str,
    required_skills: Iterable[str] = SKILL_KEYWORDS,
) -> MatchResult:
    """Compare a resume against a job description and identify missing skills."""

    description_text = _normalize_text(job_description)
    resume_text_normalized = _normalize_text(resume_text)
    required_skills_tuple = tuple(required_skills)
    missing_skills: list[str] = []
    matched_skills = 0

    for skill in required_skills_tuple:
        normalized_skill = _normalize_text(skill)
        if not normalized_skill:
            continue
        if normalized_skill in resume_text_normalized or normalized_skill in description_text:
            matched_skills += 1
        else:
            missing_skills.append(skill)

    total_skills = max(len(required_skills_tuple), 1)
    resume_score = round((matched_skills / total_skills) * 100)
    return MatchResult(
        match_score=resume_score,
        reasons=tuple(),
        missing_skills=tuple(missing_skills[:8]),
        resume_match_score=resume_score,
    )