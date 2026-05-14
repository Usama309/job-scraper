from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List

import feedparser

from src.filters import compute_job_id
from src.models import Job
from src.sources.base import HTTPClient


def _hours_to_fromage(hours: int) -> int:
    if hours <= 24:
        return 1
    if hours <= 72:
        return 3
    if hours <= 168:
        return 7
    return 30


class IndeedSource:
    NAME = "Indeed"
    ENDPOINT = "https://www.indeed.com/rss"

    def __init__(self, http: HTTPClient | None = None):
        self.http = http or HTTPClient()

    def fetch(self, *, keyword: str, time_window_hours: int) -> List[Job]:
        params = {
            "q": keyword,
            "l": "remote",
            "fromage": _hours_to_fromage(time_window_hours),
            "sort": "date",
        }
        r = self.http.get(self.ENDPOINT, params=params)
        r.raise_for_status()
        feed = feedparser.parse(r.text)
        jobs: List[Job] = []
        for entry in feed.entries:
            raw_title = entry.get("title", "")
            # Indeed RSS title format: "Job Title - Company - Location"
            parts = [p.strip() for p in raw_title.split(" - ")]
            if len(parts) < 2:
                continue
            title = parts[0]
            company = parts[1]
            location = parts[2] if len(parts) >= 3 else "Remote"
            desc = re.sub(r"<[^>]+>", "", entry.get("description", ""))[:300]
            jobs.append(Job(
                job_id=compute_job_id(title, company),
                scraped_at=datetime.now(timezone.utc),
                posted_date=entry.get("published"),
                title=title,
                company=company,
                location=location,
                remote_type="Remote" if "remote" in location.lower() else None,
                employment_type=None,
                salary_range=None,
                skills_tags=[],
                keyword_matched=keyword,
                description_snippet=desc,
                source=self.NAME,
                url=entry.get("link", ""),
            ))
        return jobs
