from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from src.filters import compute_job_id
from src.models import Job
from src.sources.base import HTTPClient


class RemoteOKSource:
    NAME = "RemoteOK"
    ENDPOINT = "https://remoteok.com/api"

    def __init__(self, http: HTTPClient | None = None):
        self.http = http or HTTPClient()

    def fetch(self, *, keyword: str, time_window_hours: int) -> List[Job]:
        # RemoteOK's ?tags filter is too strict (often returns 0 results).
        # Fetch full feed and client-side filter by keyword in title/description/tags.
        r = self.http.get(self.ENDPOINT)
        r.raise_for_status()
        payload = r.json()
        jobs: List[Job] = []
        kw_lower = keyword.lower()
        for raw in payload:
            if not isinstance(raw, dict) or "position" not in raw:
                continue
            title = raw.get("position") or ""
            company = raw.get("company") or ""
            if not title or not company:
                continue
            # Match keyword in title, description, or tags
            haystack = (
                title.lower() + " "
                + (raw.get("description") or "").lower() + " "
                + " ".join(raw.get("tags") or []).lower()
            )
            if kw_lower not in haystack:
                continue
            sal_min = raw.get("salary_min")
            sal_max = raw.get("salary_max")
            salary = None
            if sal_min or sal_max:
                salary = f"${sal_min or '?'}-${sal_max or '?'}".replace("None", "?")
            desc = (raw.get("description") or "").replace("<p>", "").replace("</p>", "")[:300]
            jobs.append(Job(
                job_id=compute_job_id(title, company),
                scraped_at=datetime.now(timezone.utc),
                posted_date=raw.get("date"),
                title=title,
                company=company,
                location=raw.get("location") or "Remote",
                remote_type="Remote",
                employment_type=None,
                salary_range=salary,
                skills_tags=raw.get("tags") or [],
                keyword_matched=keyword,
                description_snippet=desc,
                source=self.NAME,
                url=raw.get("url") or f"https://remoteok.com/remote-jobs/{raw.get('id', '')}",
            ))
        return jobs
