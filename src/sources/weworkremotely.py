from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List

import feedparser

from src.filters import compute_job_id
from src.models import Job
from src.sources.base import HTTPClient


_CATEGORIES = [
    "remote-programming-jobs",
    "remote-customer-support-jobs",
    "remote-sales-and-marketing-jobs",
    "remote-product-jobs",
    "remote-design-jobs",
]


class WeWorkRemotelySource:
    NAME = "WeWorkRemotely"
    BASE = "https://weworkremotely.com/categories"

    def __init__(self, http: HTTPClient | None = None):
        self.http = http or HTTPClient()

    def fetch(self, *, keyword: str, time_window_hours: int) -> List[Job]:
        kw = keyword.lower()
        out: List[Job] = []
        for cat in _CATEGORIES:
            url = f"{self.BASE}/{cat}/jobs.rss"
            try:
                r = self.http.get(url)
            except Exception:
                continue
            if r.status_code != 200:
                continue
            feed = feedparser.parse(r.text)
            for entry in feed.entries:
                title = entry.get("title", "")
                if kw not in title.lower() and kw not in (entry.get("description") or "").lower():
                    continue
                # WWR titles look like "Company: Role Title (Location)"
                company, _, rest = title.partition(":")
                role = rest.strip()
                m = re.search(r"\(([^)]+)\)\s*$", role)
                location = m.group(1) if m else "Remote"
                role_clean = re.sub(r"\s*\([^)]+\)\s*$", "", role).strip()
                out.append(Job(
                    job_id=compute_job_id(role_clean, company.strip()),
                    scraped_at=datetime.now(timezone.utc),
                    posted_date=entry.get("published"),
                    title=role_clean or title,
                    company=company.strip() or "Unknown",
                    location=location,
                    remote_type="Remote",
                    employment_type=None,
                    salary_range=None,
                    skills_tags=[entry.get("category")] if entry.get("category") else [],
                    keyword_matched=keyword,
                    description_snippet=(entry.get("description") or "")[:300],
                    source=self.NAME,
                    url=entry.get("link", ""),
                ))
            self.http.jitter(low=1.0, high=2.0)
        return out
