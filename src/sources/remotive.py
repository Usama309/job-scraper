from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from src.filters import compute_job_id
from src.models import Job
from src.sources.base import HTTPClient


class RemotiveSource:
    NAME = "Remotive"
    ENDPOINT = "https://remotive.com/api/remote-jobs"

    def __init__(self, http: HTTPClient | None = None):
        self.http = http or HTTPClient()

    def fetch(self, *, keyword: str, time_window_hours: int) -> List[Job]:
        r = self.http.get(self.ENDPOINT, params={"search": keyword})
        r.raise_for_status()
        payload = r.json()
        jobs: List[Job] = []
        for raw in payload.get("jobs", []):
            title = raw.get("title") or ""
            company = raw.get("company_name") or ""
            if not title or not company:
                continue
            desc = (raw.get("description") or "").replace("<p>", "").replace("</p>", "")[:300]
            jobs.append(Job(
                job_id=compute_job_id(title, company),
                scraped_at=datetime.now(timezone.utc),
                posted_date=raw.get("publication_date"),
                title=title,
                company=company,
                location=raw.get("candidate_required_location") or "Remote",
                remote_type="Remote",
                employment_type=(raw.get("job_type") or "").replace("_", "-").title() or None,
                salary_range=raw.get("salary") or None,
                skills_tags=raw.get("tags") or [],
                keyword_matched=keyword,
                description_snippet=desc,
                source=self.NAME,
                url=raw.get("url") or "",
            ))
        return jobs
