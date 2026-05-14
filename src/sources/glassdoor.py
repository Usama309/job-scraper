from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from bs4 import BeautifulSoup

from src.filters import compute_job_id
from src.models import Job
from src.sources.base import HTTPClient


class GlassdoorSource:
    NAME = "Glassdoor"

    def __init__(self, http: HTTPClient | None = None):
        self.http = http or HTTPClient()

    def fetch(self, *, keyword: str, time_window_hours: int) -> List[Job]:
        kw_slug = keyword.lower().replace(" ", "-")
        n = 7 + len(kw_slug)
        url = f"https://www.glassdoor.com/Job/remote-{kw_slug}-jobs-SRCH_IL.0,6_IS11047_KO7,{n}.htm"
        try:
            r = self.http.get(url)
        except Exception:
            return []
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        jobs: List[Job] = []
        for li in soup.select("li[data-test='jobListing']"):
            title_el = li.select_one("[data-test='job-title']")
            company_el = li.select_one("[data-test='employer-name']")
            loc_el = li.select_one("[data-test='emp-location']")
            sal_el = li.select_one("[data-test='detailSalary']")
            link_el = li.select_one("a[data-test='job-link']")
            if not (title_el and company_el):
                continue
            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True)
            link = link_el.get("href", "") if link_el else ""
            if link and link.startswith("/"):
                link = f"https://www.glassdoor.com{link}"
            jobs.append(Job(
                job_id=compute_job_id(title, company),
                scraped_at=datetime.now(timezone.utc),
                posted_date=None,
                title=title,
                company=company,
                location=(loc_el.get_text(strip=True) if loc_el else "Remote"),
                remote_type="Remote",
                employment_type=None,
                salary_range=(sal_el.get_text(strip=True) if sal_el else None),
                skills_tags=[],
                keyword_matched=keyword,
                description_snippet="",
                source=self.NAME,
                url=link,
            ))
        return jobs
