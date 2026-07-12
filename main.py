"""Application entry point for AI-Job-Alert-Bot."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from config import load_settings
from crawler import BaseCrawler
from database import alert_already_sent, initialize_database, insert_job, is_duplicate_job, record_alert
from filters import JobFilter
from notifier import TelegramNotifier
from notifier.telegram import _escape_markdown, _sanitize_url
from utils import load_resume_text, score_job, score_resume_match
from utils import is_priority_company, load_priority_companies
from sources import (
    AshbyCrawler,
    CompanyCareerPageCrawler,
    GreenhouseCrawler,
    LeverCrawler,
    LinkedInJobsCrawler,
    WellfoundCrawler,
    YCJobsCrawler,
)

LOGGER = logging.getLogger(__name__)
STATE_DIRECTORY = Path("state")
SOURCE_CONFIG_PATH = STATE_DIRECTORY / "sources.json"
PRIORITY_KEYWORDS = (
    "ai",
    "ml",
    "machine learning",
    "llm",
    "genai",
    "research",
)


def _configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def _load_source_configs() -> list[dict[str, Any]]:
    source_configs_raw = os.getenv("SOURCES_CONFIG", "").strip()
    if source_configs_raw:
        return json.loads(source_configs_raw)

    if SOURCE_CONFIG_PATH.exists():
        return json.loads(SOURCE_CONFIG_PATH.read_text(encoding="utf-8"))

    return []


def _build_crawler(config: dict[str, Any]) -> BaseCrawler:
    source_type = str(config.get("source", "")).strip().lower()

    if source_type == "greenhouse":
        return GreenhouseCrawler(
            board_token=str(config["board_token"]),
            company=config.get("company"),
        )
    if source_type == "lever":
        return LeverCrawler(
            company_slug=str(config["company_slug"]),
            company=config.get("company"),
        )
    if source_type == "ashby":
        return AshbyCrawler(
            career_page_url=str(config["career_page_url"]),
            company=str(config["company"]),
        )
    if source_type == "linkedin":
        return LinkedInJobsCrawler(
            search_url=str(config["search_url"]),
            company=config.get("company", "LinkedIn"),
        )
    if source_type == "wellfound":
        return WellfoundCrawler(
            company_slug=str(config["company_slug"]),
            company=str(config["company"]),
        )
    if source_type == "yc":
        return YCJobsCrawler(
            company_slug=config.get("company_slug"),
            jobs_url=config.get("jobs_url"),
            company=config.get("company"),
        )
    if source_type == "career_page":
        return CompanyCareerPageCrawler(
            career_page_url=str(config["career_page_url"]),
            company=str(config["company"]),
        )

    raise ValueError(f"Unsupported source type: {source_type}")


def _build_alert_message(job: Any) -> str:
    scoring = score_job(
        title=job.title,
        company=job.company,
        description=getattr(job, "description", ""),
        location=getattr(job, "location", "Remote"),
    )
    resume_text = getattr(job, "resume_text", "")
    resume_match = (
        score_resume_match(
            job_description=f"{job.title} {getattr(job, 'description', '')}",
            resume_text=resume_text,
        )
        if resume_text
        else None
    )

    lines = [
        "🚀 *New Opportunity*",
        "",
        f"🔥 *Match Score:* {scoring.match_score}%",
        f"🏢 *Company:* {_escape_markdown(job.company)}",
        f"💼 *Role:* {_escape_markdown(job.title)}",
        f"📍 *Location:* {_escape_markdown(getattr(job, 'location', 'Remote'))}",
        f"🌐 *Source:* {_escape_markdown(job.source)}",
        f"🔗 *Apply:* [{_escape_markdown('Open posting')}]({_sanitize_url(job.url)})",
    ]

    if scoring.reasons:
        lines.extend(["", "*Reasons:"])
        lines.extend([f"✓ {_escape_markdown(reason)}" for reason in scoring.reasons[:6]])

    if resume_match and resume_match.resume_match_score is not None:
        lines.extend(["", f"📄 *Resume Match:* {resume_match.resume_match_score}%"])
        if resume_match.missing_skills:
            lines.append(f"*Missing:* {_escape_markdown(', '.join(resume_match.missing_skills))}")

    return "\n".join(lines)


def _is_priority_job(job: Any, priority_companies: tuple[str, ...]) -> bool:
    if is_priority_company(job.company, priority_companies):
        return True
    text = f"{job.title} {job.company} {job.source}".lower()
    return any(keyword in text for keyword in PRIORITY_KEYWORDS)


def run() -> int:
    """Execute one crawl-and-notify cycle."""

    settings = load_settings()
    _configure_logging(settings.log_level)
    initialize_database()
    resume_text = load_resume_text(getattr(settings, "resume_path", None))
    priority_companies = load_priority_companies()

    job_filter = JobFilter()
    notifier = TelegramNotifier(token=settings.telegram_token, chat_id=settings.chat_id)

    source_configs = _load_source_configs()
    if not source_configs:
        LOGGER.warning("No source configuration found; nothing to crawl")
        return 0

    crawlers = [_build_crawler(config) for config in source_configs]
    total_jobs = 0
    total_skipped = 0
    total_alerts = 0

    for crawler in crawlers:
        LOGGER.info("Crawling %s", crawler.display_name)
        try:
            jobs = crawler.crawl()
        except Exception:
            LOGGER.exception("Crawler failed for %s", crawler.display_name)
            continue

        LOGGER.info("Found %d jobs from %s", len(jobs), crawler.display_name)

        for job in jobs:
            total_jobs += 1
            if not job_filter.should_keep(job.title, job.company, location=""):
                total_skipped += 1
                LOGGER.info("Skipped job by filter: %s | %s", job.company, job.title)
                continue

            if is_duplicate_job(job):
                total_skipped += 1
                LOGGER.info("Skipped duplicate job: %s | %s", job.company, job.title)
                continue

            stored_row_id = insert_job(job)
            alert_key = job.job_id or job.job_hash or f"job-{stored_row_id}"
            if alert_already_sent(job_id=alert_key):
                total_skipped += 1
                LOGGER.info("Skipped already-alerted job: %s | %s", job.company, job.title)
                continue

            if _is_priority_job(job, priority_companies):
                sent = notifier.send_priority_alert(
                    company=job.company,
                    role=job.title,
                    location="Remote",
                    source=job.source,
                    apply_url=job.url,
                )
            else:
                if resume_text:
                    setattr(job, "resume_text", resume_text)
                sent = notifier.send_message(_build_alert_message(job))

            record_alert(
                job_id=alert_key,
                channel="telegram",
                status="sent" if sent else "failed",
                payload=job.url,
            )

            if sent:
                total_alerts += 1
                LOGGER.info("Telegram sent: %s | %s", job.company, job.title)
            else:
                LOGGER.error("Telegram failed: %s | %s", job.company, job.title)

    LOGGER.info(
        "Run complete: jobs=%d skipped=%d alerts=%d",
        total_jobs,
        total_skipped,
        total_alerts,
    )
    return 0


def main() -> None:
    """CLI entry point."""

    raise SystemExit(run())


if __name__ == "__main__":
    main()
