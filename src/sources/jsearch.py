from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List

from src.filters import compute_job_id
from src.models import Job
from src.sources.base import HTTPClient


class JSearchSource:
    NAME = "JSearch"
    ENDPOINT = "https://jsearch.p.rapidapi.com/search"

    def __init__(self, http: HTTPClient | None = None):
        self.http = http or HTTPClient()
        self.key = os.environ.get("RAPIDAPI_KEY", "")

    def fetch_combined(self, *, keywords: List[str], time_window_hours: int) -> List[Job]:
        if not self.key:
            raise RuntimeError("RAPIDAPI_KEY not set")
        query = " OR ".join(keywords[:10])  # API supports OR; cap to keep query string sane
        date_posted = "today" if time_window_hours <= 24 else ("3days" if time_window_hours <= 72 else "week")
        params = {
            "query": f"{query} remote",
            "page": "1",
            "num_pages": "1",
            "date_posted": date_posted,
            "remote_jobs_only": "true",
        }
        headers = {
            "X-RapidAPI-Key": self.key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        }
        r = self.http.get(self.ENDPOINT, params=params, headers=headers)
        r.raise_for_status()
        payload = r.json()
        jobs: List[Job] = []
        for raw in payload.get("data", []):
            title = raw.get("job_title") or ""
            company = raw.get("employer_name") or ""
            if not title or not company:
                continue
            publishers = [opt.get("publisher", "") for opt in (raw.get("apply_options") or [])]
            primary_pub = publishers[0] if publishers else "Unknown"
            sal_min = raw.get("job_min_salary")
            sal_max = raw.get("job_max_salary")
            salary = f"${sal_min}-${sal_max}" if sal_min and sal_max else None
            jobs.append(Job(
                job_id=compute_job_id(title, company),
                scraped_at=datetime.now(timezone.utc),
                posted_date=raw.get("job_posted_at_datetime_utc"),
                title=title,
                company=company,
                location=f"Remote ({raw.get('job_country') or ''})".strip(" ()"),
                remote_type="Remote" if raw.get("job_is_remote") else None,
                employment_type=raw.get("job_employment_type"),
                salary_range=salary,
                skills_tags=publishers,
                keyword_matched=f"JSearch via {primary_pub}",
                description_snippet=(raw.get("job_description") or "")[:300],
                source=self.NAME,
                url=raw.get("job_apply_link") or "",
                company_website=raw.get("employer_website"),
            ))
        return jobs
