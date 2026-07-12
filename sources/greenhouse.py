"""Greenhouse Jobs crawler."""

from __future__ import annotations

from crawler.base import BaseCrawler
from database import JobRecord


class GreenhouseCrawler(BaseCrawler):
    """Crawler for Greenhouse boards-api job feeds."""

    source_name = "greenhouse"
    display_name = "Greenhouse"

    def __init__(self, board_token: str, company: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.board_token = board_token
        self.company = company or board_token

    @property
    def feed_url(self) -> str:
        return f"https://boards-api.greenhouse.io/v1/boards/{self.board_token}/jobs?content=true"

    def crawl(self) -> list[JobRecord]:
        payload = self._get_json(self.feed_url)
        jobs = []
        for item in payload.get("jobs", []):
            jobs.append(
                {
                    "job_id": str(item.get("id", "")),
                    "company": self.company,
                    "title": str(item.get("title", "")).strip(),
                    "url": str(item.get("absolute_url", "")).strip(),
                    "location": "Remote",
                }
            )
        return self._build_job_records(jobs, self.company, self.display_name)