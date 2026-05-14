from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from src.filters import compute_job_id
from src.models import Job
from src.sources.base import HTTPClient


def _load_country_codes() -> List[str]:
    cfg = Path(__file__).resolve().parent.parent.parent / "config" / "countries.json"
    try:
        return json.loads(cfg.read_text()).get("adzuna_countries", ["us"])
    except Exception:
        return ["us"]


class AdzunaSource:
    NAME = "Adzuna"
    ENDPOINT_TMPL = "https://api.adzuna.com/v1/api/jobs/{cc}/search/1"

    def __init__(self, http: HTTPClient | None = None):
        self.http = http or HTTPClient()
        self.app_id = os.environ.get("ADZUNA_APP_ID", "")
        self.app_key = os.environ.get("ADZUNA_APP_KEY", "")
        self.country_codes = _load_country_codes()

    def fetch_combined(self, *, keywords: List[str], time_window_hours: int) -> List[Job]:
        """One API call per supported country with all keywords as OR query.

        Country list comes from config/countries.json. Quota-respecting:
        free tier is 250 calls/month total, and we use len(countries) per run.
        """
        if not self.app_id or not self.app_key:
            raise RuntimeError("ADZUNA_APP_ID / ADZUNA_APP_KEY not set")
        jobs: List[Job] = []
        for cc in self.country_codes:
            jobs.extend(self._fetch_one_country(cc, keywords, time_window_hours))
        return jobs

    def _fetch_one_country(self, cc: str, keywords: List[str], time_window_hours: int) -> List[Job]:
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "results_per_page": 50,
            "what_or": " ".join(keywords),
            "max_days_old": max(1, time_window_hours // 24 or 1),
        }
        try:
            r = self.http.get(self.ENDPOINT_TMPL.format(cc=cc), params=params)
            r.raise_for_status()
        except Exception:
            return []
        payload = r.json()
        jobs: List[Job] = []
        for raw in payload.get("results", []):
            title = raw.get("title") or ""
            company = (raw.get("company") or {}).get("display_name") or ""
            if not title or not company:
                continue
            loc = (raw.get("location") or {}).get("display_name") or ""
            desc = raw.get("description") or ""
            # Adzuna doesn't tag remote in API; infer from title/description/location.
            looks_remote = (
                "remote" in title.lower()
                or "remote" in loc.lower()
                or "remote" in desc.lower()[:500]
                or "work from home" in desc.lower()[:500]
            )
            if not looks_remote:
                continue
            # Normalize location: include "Remote" prefix so downstream is_remote() matches
            loc = loc if "remote" in loc.lower() else (f"Remote ({loc})" if loc else "Remote")
            sal_min = raw.get("salary_min")
            sal_max = raw.get("salary_max")
            salary = f"{sal_min}-{sal_max}" if sal_min and sal_max else (str(sal_min or sal_max) if (sal_min or sal_max) else None)
            jobs.append(Job(
                job_id=compute_job_id(title, company),
                scraped_at=datetime.now(timezone.utc),
                posted_date=raw.get("created"),
                title=title,
                company=company,
                location=f"{loc} — {cc.upper()}" if cc.upper() not in loc.upper() else loc,
                remote_type="Remote",
                employment_type=raw.get("contract_type"),
                salary_range=salary,
                skills_tags=[cc.upper()],
                keyword_matched=", ".join(keywords)[:60],
                description_snippet=(raw.get("description") or "")[:300],
                source=self.NAME,
                url=raw.get("redirect_url") or "",
            ))
        return jobs
