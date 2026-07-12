"""Lever Jobs crawler."""

from __future__ import annotations

from crawler.base import BaseCrawler
from database import JobRecord


class LeverCrawler(BaseCrawler):
    """Crawler for Lever postings APIs."""

    source_name = "lever"
    display_name = "Lever"

    def __init__(self, company_slug: str, company: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.company_slug = company_slug
        self.company = company or company_slug

    @property
    def feed_url(self) -> str:
        return f"https://api.lever.co/v0/postings/{self.company_slug}?mode=json"

    def crawl(self) -> list[JobRecord]:
        payload = self._get_json(self.feed_url)
        jobs = []
        for item in payload:
            jobs.append(
                {
                    "job_id": str(item.get("id", "")),
                    "company": self.company,
                    "title": str(item.get("text", "")).strip(),
                    "url": str(item.get("hostedUrl", "")).strip(),
                    "location": str(item.get("categories", {}).get("location", "Remote")),
                }
            )
        return self._build_job_records(jobs, self.company, self.display_name)