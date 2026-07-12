"""Official company career page crawler."""

from __future__ import annotations

from crawler.base import BaseCrawler
from database import JobRecord


class CompanyCareerPageCrawler(BaseCrawler):
    """Best-effort crawler for official careers pages."""

    source_name = "career_page"
    display_name = "Company Career Page"

    def __init__(self, career_page_url: str, company: str, **kwargs):
        super().__init__(**kwargs)
        self.career_page_url = career_page_url.rstrip("/")
        self.company = company

    def crawl(self) -> list[JobRecord]:
        html = self._get(self.career_page_url).text
        jobs = self._extract_json_ld_job_postings(html, self.career_page_url)
        return self._build_job_records(jobs, self.company, self.display_name)