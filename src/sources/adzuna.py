from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List

from src.filters import compute_job_id
from src.models import Job
from src.sources.base import HTTPClient


class AdzunaSource:
    NAME = "Adzuna"
    ENDPOINT = "https://api.adzuna.com/v1/api/jobs/us/search/1"

    def __init__(self, http: HTTPClient | None = None):
        self.http = http or HTTPClient()
        self.app_id = os.environ.get("ADZUNA_APP_ID", "")
        self.app_key = os.environ.get("ADZUNA_APP_KEY", "")

    def fetch_combined(self, *, keywords: List[str], time_window_hours: int) -> List[Job]:
        """One API call with all keywords as OR query (quota-respecting)."""
        if not self.app_id or not self.app_key:
            raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY not set")
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": 50,
            "what_or": " ".join(keywords),
            "where": "remote",
            "max_days_old": max(1, time_window_hours // 24 or 1),
        }
        r = self.http.get(self.ENDPOINT, params=params)
        r.raise_for_status()
        payload = r.json()
        jobs: List[Job] = []
        for raw in payload.get("results", []):
            title = raw.get("title") or ""
            company = (raw.get("company") or {}).get("display_name") or ""
            if not title or not company:
                continue
            loc = (raw.get("location") or {}).get("display_name") or "Remote"
            sal_min = raw.get("salary_min")
            sal_max = raw.get("salary_max")
            salary = f"{sal_min}-{sal_max}" if sal_min and sal_max else (str(sal_min or sal_max) if (sal_min or sal_max) else None)
            jobs.append(Job(
                job_id=compute_job_id(title, company),
                scraped_at=datetime.now(timezone.utc),
                posted_date=raw.get("created"),
                title=title,
                company=company,
                location=loc,
                remote_type="Remote",
                employment_type=raw.get("contract_type"),
                salary_range=salary,
                skills_tags=[],
                keyword_matched=", ".join(keywords)[:60],
                description_snippet=(raw.get("description") or "")[:300],
                source=self.NAME,
                url=raw.get("redirect_url") or "",
            ))
        return jobs
