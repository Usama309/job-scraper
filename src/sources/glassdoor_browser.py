"""Glassdoor scraper via Comet. Detects Cloudflare/Captcha and pings ntfy.

Multi-country: rotates through Glassdoor's country domains (glassdoor.co.uk,
glassdoor.de, glassdoor.fr, etc.) per config/countries.json.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from src.comet_client import BlockedError, fetch_page_html
from src.filters import compute_job_id
from src.models import Job


def _load_countries() -> dict:
    cfg = Path(__file__).resolve().parent.parent.parent / "config" / "countries.json"
    return json.loads(cfg.read_text())


class GlassdoorBrowserSource:
    NAME = "Glassdoor"

    def __init__(self):
        self.ntfy_topic = os.environ.get("NTFY_TOPIC", "")
        self.countries = _load_countries()["glassdoor_domains"]

    def fetch(self, *, keyword: str, time_window_hours: int) -> List[Job]:
        from_age = min(30, max(1, time_window_hours // 24 or 1))
        all_jobs: List[Job] = []
        for country, domain in self.countries.items():
            url = (
                f"https://{domain}/Job/jobs.htm?"
                f"sc.keyword={quote_plus(keyword)}"
                f"&fromAge={from_age}"
                f"&remoteWorkType=1"
            )
            try:
                html = fetch_page_html(
                    url,
                    ntfy_topic=self.ntfy_topic,
                    label=f"Glassdoor {country} ({keyword})",
                )
                all_jobs.extend(self._parse(html, keyword, country, domain))
            except BlockedError:
                continue
            except Exception:
                continue
            time.sleep(2)  # gentle pacing — Glassdoor is sensitive
        return all_jobs

    def _parse(self, html: str, keyword: str, country: str, domain: str) -> List[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []
        cards = (
            soup.select("li[data-test='jobListing']")
            or soup.select("li.react-job-listing")
            or soup.select("li.JobsList_jobListItem__wjTHv")
        )
        seen_ids = set()
        for card in cards:
            title_el = card.select_one("[data-test='job-title'], a[data-test='job-link']")
            company_el = card.select_one("[data-test='employer-name'], [class*='EmployerProfile']")
            loc_el = card.select_one("[data-test='emp-location'], [class*='location']")
            sal_el = card.select_one("[data-test='detailSalary'], [data-test='salary-estimate']")
            link_el = card.select_one("a[data-test='job-link'], a[href*='/job-listing/']")
            desc_el = card.select_one("[data-test='job-description'], [class*='JobDetails']")

            if not title_el or not company_el:
                continue
            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True)
            location = loc_el.get_text(strip=True) if loc_el else ""
            desc = desc_el.get_text(" ", strip=True) if desc_el else ""
            loose_remote = (
                "remote" in title.lower()
                or "remote" in location.lower()
                or "remote" in desc.lower()
            )
            href = link_el.get("href", "") if link_el else ""
            if href.startswith("/"):
                href = f"https://{domain}{href}"

            jid = compute_job_id(title, company)
            if jid in seen_ids:
                continue
            seen_ids.add(jid)

            loc_with_country = (
                f"{location} — {country}" if country and country not in location else (location or country)
            )

            jobs.append(Job(
                job_id=jid,
                scraped_at=datetime.now(timezone.utc),
                posted_date=None,
                title=title,
                company=company,
                location=loc_with_country or "Remote",
                remote_type="Remote" if loose_remote else None,
                employment_type=None,
                salary_range=sal_el.get_text(strip=True) if sal_el else None,
                skills_tags=[country] if country else [],
                keyword_matched=keyword,
                description_snippet=desc[:300],
                source=self.NAME,
                url=href,
            ))
        return jobs
