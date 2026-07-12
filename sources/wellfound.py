"""Wellfound jobs crawler."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler.base import BaseCrawler
from database import JobRecord


class WellfoundCrawler(BaseCrawler):
    """Crawler for Wellfound job listings pages."""

    source_name = "wellfound"
    display_name = "Wellfound"

    def __init__(self, company_slug: str, company: str, **kwargs):
        super().__init__(**kwargs)
        self.company_slug = company_slug.strip("/")
        self.company = company

    @property
    def listing_url(self) -> str:
        return f"https://wellfound.com/company/{self.company_slug}/jobs"

    def crawl(self) -> list[JobRecord]:
        html = self._get(self.listing_url).text
        jobs: list[dict[str, str]] = []
        soup = BeautifulSoup(html, "html.parser")

        for anchor in soup.select('a[href*="/jobs/"]'):
            title = anchor.get_text(" ", strip=True)
            href = anchor.get("href", "")
            if not title or not href:
                continue
            jobs.append(
                {
                    "job_id": href,
                    "company": self.company,
                    "title": title,
                    "url": urljoin(self.listing_url, href),
                    "location": "Remote",
                }
            )

        if not jobs:
            jobs = self._extract_json_ld_job_postings(html, self.listing_url)

        return self._build_job_records(jobs, self.company, self.display_name)