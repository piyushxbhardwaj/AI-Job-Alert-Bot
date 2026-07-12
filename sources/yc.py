"""YC Jobs crawler."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler.base import BaseCrawler
from database import JobRecord


class YCJobsCrawler(BaseCrawler):
    """Crawler for Y Combinator jobs pages."""

    source_name = "yc"
    display_name = "YC Jobs"

    def __init__(self, company_slug: str | None = None, jobs_url: str | None = None, company: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.company_slug = company_slug.strip("/") if company_slug else None
        self.jobs_url = jobs_url.rstrip("/") if jobs_url else None
        self.company = company or (company_slug or "YC")

    @property
    def listing_url(self) -> str:
        if self.jobs_url:
            return self.jobs_url
        if self.company_slug:
            return f"https://www.ycombinator.com/companies/{self.company_slug}/jobs"
        return "https://www.ycombinator.com/jobs"

    def crawl(self) -> list[JobRecord]:
        html = self._get(self.listing_url).text
        soup = BeautifulSoup(html, "html.parser")
        jobs: list[dict[str, str]] = []

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