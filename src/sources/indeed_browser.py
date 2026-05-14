"""Indeed scraper that runs through Comet (real Chrome) instead of direct HTTP.

Use this from `scripts/scrape_local.py` only — it requires Comet running with
CDP enabled on localhost:9222. The regular `indeed.py` is HTTP-based and gets
403'd from datacenter/Pakistan IPs.
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import List
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from src.comet_client import fetch_page_html
from src.filters import compute_job_id
from src.models import Job


def _hours_to_fromage(hours: int) -> int:
    if hours <= 24:
        return 1
    if hours <= 72:
        return 3
    if hours <= 168:
        return 7
    return 30


class IndeedBrowserSource:
    NAME = "Indeed"

    def __init__(self):
        self.ntfy_topic = os.environ.get("NTFY_TOPIC", "")

    def fetch(self, *, keyword: str, time_window_hours: int) -> List[Job]:
        fromage = _hours_to_fromage(time_window_hours)
        url = (
            f"https://www.indeed.com/jobs?q={quote_plus(keyword)}"
            f"&l=Remote&fromage={fromage}&sort=date"
        )
        html = fetch_page_html(
            url,
            ntfy_topic=self.ntfy_topic,
            label=f"Indeed ({keyword})",
        )
        return self._parse(html, keyword)

    def _parse(self, html: str, keyword: str) -> List[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []
        # Indeed wraps each result in div.job_seen_beacon / div.cardOutline.
        # The data-jk attribute lives on the <a> inside, not the wrapper.
        cards = soup.select("div.job_seen_beacon") or soup.select("div.cardOutline")
        seen_ids = set()
        for card in cards:
            link_el = card.select_one("a[data-jk]")
            jk = (link_el.get("data-jk") if link_el else "") or ""
            title_el = card.select_one("h2.jobTitle, span[id^='jobTitle']")
            company_el = card.select_one("[data-testid='company-name'], span.companyName")
            loc_el = card.select_one("[data-testid='text-location'], div.companyLocation")
            sal_el = card.select_one("[data-testid='attribute_snippet_testid'], div.salary-snippet")
            posted_el = card.select_one("[data-testid='myJobsStateDate'], span.date")

            if not title_el or not company_el:
                continue
            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True)
            location = (loc_el.get_text(strip=True) if loc_el else "") or "Remote"
            href = link_el.get("href", "") if link_el else ""
            if href and href.startswith("/"):
                href = f"https://www.indeed.com{href}"
            elif not href and jk:
                href = f"https://www.indeed.com/viewjob?jk={jk}"

            jid = compute_job_id(title, company)
            if jid in seen_ids:
                continue
            seen_ids.add(jid)

            jobs.append(Job(
                job_id=jid,
                scraped_at=datetime.now(timezone.utc),
                posted_date=posted_el.get_text(strip=True) if posted_el else None,
                title=title,
                company=company,
                location=location,
                remote_type="Remote" if "remote" in location.lower() else None,
                employment_type=None,
                salary_range=sal_el.get_text(strip=True) if sal_el else None,
                skills_tags=[],
                keyword_matched=keyword,
                description_snippet="",
                source=self.NAME,
                url=href,
            ))
        return jobs
