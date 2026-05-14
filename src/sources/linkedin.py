from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from bs4 import BeautifulSoup

from src.filters import compute_job_id
from src.models import Job
from src.sources.base import HTTPClient


class LinkedInSource:
    NAME = "LinkedIn"
    ENDPOINT = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def __init__(self, http: HTTPClient | None = None):
        self.http = http or HTTPClient()

    def fetch(self, *, keyword: str, time_window_hours: int) -> List[Job]:
        seconds = max(3600, time_window_hours * 3600)
        params = {
            "keywords": keyword,
            "location": "Worldwide",
            "f_TPR": f"r{seconds}",
            "f_WT": "2",  # remote
            "start": 0,
        }
        all_jobs: List[Job] = []
        seen_ids: set[str] = set()
        for start in (0, 25, 50):
            params["start"] = start
            r = self.http.get(self.ENDPOINT, params=params)
            if r.status_code != 200:
                break
            soup = BeautifulSoup(r.text, "html.parser")
            cards = soup.select("li") or soup.select("div.base-card")
            page_jobs: List[Job] = []
            for card in cards:
                title_el = card.select_one(".base-search-card__title")
                company_el = card.select_one(".base-search-card__subtitle")
                loc_el = card.select_one(".job-search-card__location")
                link_el = card.select_one("a.base-card__full-link")
                date_el = card.select_one("time")
                if not (title_el and company_el):
                    continue
                title = title_el.get_text(strip=True)
                company = company_el.get_text(strip=True)
                location = (loc_el.get_text(strip=True) if loc_el else "") or "Remote"
                url = (link_el.get("href") if link_el else "") or ""
                posted = (date_el.get("datetime") if date_el else None)
                job_id = compute_job_id(title, company)
                if job_id in seen_ids:
                    continue
                seen_ids.add(job_id)
                page_jobs.append(Job(
                    job_id=job_id,
                    scraped_at=datetime.now(timezone.utc),
                    posted_date=posted,
                    title=title,
                    company=company,
                    location=location,
                    remote_type="Remote",
                    employment_type=None,
                    salary_range=None,
                    skills_tags=[],
                    keyword_matched=keyword,
                    description_snippet="",
                    source=self.NAME,
                    url=url,
                ))
            if not page_jobs:
                break
            all_jobs.extend(page_jobs)
            self.http.jitter()
        return all_jobs
