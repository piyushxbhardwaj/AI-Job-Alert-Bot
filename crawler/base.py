"""Base crawler abstractions for AI-Job-Alert-Bot."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import logging
from typing import Any, ClassVar

import requests

from database import JobRecord

LOGGER = logging.getLogger(__name__)

_CRAWLER_REGISTRY: dict[str, type[BaseCrawler]] = {}


class BaseCrawler(ABC):
    """Common interface for all job source crawlers."""

    source_name: ClassVar[str]
    display_name: ClassVar[str]
    default_timeout: ClassVar[float] = 15.0

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        source_name = getattr(cls, "source_name", "").strip()
        if source_name:
            _CRAWLER_REGISTRY[source_name] = cls

    def __init__(self, timeout: float | None = None, session: requests.Session | None = None) -> None:
        self.timeout = timeout if timeout is not None else self.default_timeout
        self.session = session or requests.Session()

    @abstractmethod
    def crawl(self) -> list[JobRecord]:
        """Return normalized job records for the source."""

    @classmethod
    def registered_crawlers(cls) -> dict[str, type[BaseCrawler]]:
        """Return the registered crawler classes keyed by source name."""

        return dict(_CRAWLER_REGISTRY)

    def _get(self, url: str) -> requests.Response:
        """Perform an HTTP GET with consistent timeout and headers."""

        response = self.session.get(
            url,
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AI-Job-Alert-Bot/1.0)"},
        )
        response.raise_for_status()
        return response

    def _get_json(self, url: str) -> Any:
        """Fetch JSON from a remote endpoint."""

        return self._get(url).json()

    def _extract_json_ld_job_postings(self, html: str, source_url: str) -> list[dict[str, str]]:
        """Extract schema.org JobPosting entries from a HTML document."""

        import re
        from bs4 import BeautifulSoup

        results: list[dict[str, str]] = []
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            content = (script.string or script.get_text(strip=True) or "").strip()
            if not content:
                continue
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                continue

            candidates = parsed if isinstance(parsed, list) else [parsed]
            for candidate in candidates:
                if isinstance(candidate, dict) and candidate.get("@type") == "JobPosting":
                    title = str(candidate.get("title", "")).strip()
                    hiring_organization = candidate.get("hiringOrganization", {})
                    company = ""
                    if isinstance(hiring_organization, dict):
                        company = str(hiring_organization.get("name", "")).strip()

                    job_location = candidate.get("jobLocation", {})
                    location = ""
                    if isinstance(job_location, dict):
                        address = job_location.get("address", {})
                        if isinstance(address, dict):
                            location = ", ".join(
                                part
                                for part in [
                                    str(address.get("addressLocality", "")).strip(),
                                    str(address.get("addressRegion", "")).strip(),
                                    str(address.get("addressCountry", "")).strip(),
                                ]
                                if part
                            )

                    results.append(
                        {
                            "job_id": str(candidate.get("identifier", "") or candidate.get("url", "") or title),
                            "company": company,
                            "title": title,
                            "url": str(candidate.get("url", source_url)).strip(),
                            "location": location or "Remote",
                        }
                    )

        if results:
            return results

        job_cards = soup.find_all(attrs={"data-job-id": True})
        for card in job_cards:
            title = card.get_text(" ", strip=True)
            job_id = card.get("data-job-id") or title
            link = card.find("a", href=True)
            results.append(
                {
                    "job_id": str(job_id),
                    "company": "",
                    "title": title,
                    "url": link["href"] if link else source_url,
                    "location": "Remote",
                }
            )

        return results

    def _build_job_records(
        self,
        jobs: list[dict[str, str]],
        company: str,
        source: str,
    ) -> list[JobRecord]:
        """Normalize raw job dictionaries into database-ready records."""

        from datetime import datetime, timezone
        from hashlib import sha256

        timestamp = datetime.now(timezone.utc).isoformat()
        date_found = timestamp.split("T", maxsplit=1)[0]

        records: list[JobRecord] = []
        for job in jobs:
            job_id = job.get("job_id") or None
            title = job.get("title", "").strip()
            url = job.get("url", "").strip()
            normalized_company = job.get("company", company).strip() or company
            job_hash = sha256(f"{normalized_company}|{title}|{url}".encode("utf-8")).hexdigest()
            records.append(
                JobRecord(
                    job_id=job_id,
                    company=normalized_company,
                    title=title,
                    url=url,
                    source=source,
                    date_found=job.get("date_found", date_found),
                    timestamp=job.get("timestamp", timestamp),
                    job_hash=job_hash,
                )
            )

        return records