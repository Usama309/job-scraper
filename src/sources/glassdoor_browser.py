"""Glassdoor scraper via Comet. Detects Cloudflare/Captcha and pings ntfy."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import List
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from src.comet_client import fetch_page_html
from src.filters import compute_job_id
from src.models import Job


class GlassdoorBrowserSource:
    NAME = "Glassdoor"

    def __init__(self):
        self.ntfy_topic = os.environ.get("NTFY_TOPIC", "")

    def fetch(self, *, keyword: str, time_window_hours: int) -> List[Job]:
        url = (
            f"https://www.glassdoor.com/Job/jobs.htm?"
            f"sc.keyword={quote_plus(keyword)}"
            f"&fromAge={min(30, max(1, time_window_hours // 24 or 1))}"
            f"&remoteWorkType=1"
        )
        html = fetch_page_html(
            url,
            ntfy_topic=self.ntfy_topic,
            label=f"Glassdoor ({keyword})",
        )
        return self._parse(html, keyword)

    def _parse(self, html: str, keyword: str) -> List[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []
        # Glassdoor renders job cards under li[data-test=jobListing] or li.react-job-listing
        cards = (
            soup.select("li[data-test='jobListing']")
            or soup.select("li.react-job-listing")
            or soup.select("[data-test='job-link']")
        )
        seen_ids = set()
        for card in cards:
            title_el = card.select_one("[data-test='job-title'], a[data-test='job-link']")
            company_el = card.select_one("[data-test='employer-name'], [class*='EmployerProfile']")
            loc_el = card.select_one("[data-test='emp-location'], [class*='location']")
            sal_el = card.select_one("[data-test='detailSalary'], [data-test='salary-estimate']")
            link_el = card.select_one("a[data-test='job-link'], a[href*='/job-listing/']")

            if not title_el or not company_el:
                continue
            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True)
            href = link_el.get("href", "") if link_el else ""
            if href.startswith("/"):
                href = f"https://www.glassdoor.com{href}"

            jid = compute_job_id(title, company)
            if jid in seen_ids:
                continue
            seen_ids.add(jid)

            jobs.append(Job(
                job_id=jid,
                scraped_at=datetime.now(timezone.utc),
                posted_date=None,
                title=title,
                company=company,
                location=loc_el.get_text(strip=True) if loc_el else "Remote",
                remote_type="Remote",
                employment_type=None,
                salary_range=sal_el.get_text(strip=True) if sal_el else None,
                skills_tags=[],
                keyword_matched=keyword,
                description_snippet="",
                source=self.NAME,
                url=href,
            ))
        return jobs
