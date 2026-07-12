"""LinkedIn Jobs crawler."""

from __future__ import annotations

from crawler.base import BaseCrawler
from database import JobRecord


class LinkedInJobsCrawler(BaseCrawler):
    """Best-effort crawler for LinkedIn job search pages."""

    source_name = "linkedin"
    display_name = "LinkedIn Jobs"

    def __init__(self, search_url: str, company: str = "LinkedIn", **kwargs):
        super().__init__(**kwargs)
        self.search_url = search_url
        self.company = company

    def crawl(self) -> list[JobRecord]:
        html = self._get(self.search_url).text
        jobs = self._extract_json_ld_job_postings(html, self.search_url)
        return self._build_job_records(jobs, self.company, self.display_name)