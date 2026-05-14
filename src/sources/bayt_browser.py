"""Bayt.com scraper via Comet. Bayt is the dominant Gulf-region job aggregator
(UAE, Saudi, Qatar, Bahrain, Kuwait, Oman). Their HTML page renders fine in
a real browser; geofencing isn't a problem because Bayt is Gulf-native.

Multi-country: Bayt uses URL paths like /en/uae-jobs/ to scope by country.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import List
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from src.comet_client import BlockedError, fetch_page_html
from src.filters import compute_job_id
from src.models import Job


# Bayt path slugs per Gulf country
_COUNTRY_PATHS = {
    "United Arab Emirates": "uae-jobs",
    "Saudi Arabia": "saudi-arabia-jobs",
    "Qatar": "qatar-jobs",
    "Bahrain": "bahrain-jobs",
    "Kuwait": "kuwait-jobs",
    "Oman": "oman-jobs",
}


class BaytBrowserSource:
    NAME = "Bayt"

    def __init__(self):
        self.ntfy_topic = os.environ.get("NTFY_TOPIC", "")

    def fetch(self, *, keyword: str, time_window_hours: int) -> List[Job]:
        all_jobs: List[Job] = []
        for country, path in _COUNTRY_PATHS.items():
            # Bayt URL: https://www.bayt.com/en/uae/jobs/<keyword>-jobs/
            kw_slug = keyword.lower().replace(" ", "-")
            url = f"https://www.bayt.com/en/{path}/?text={quote_plus(keyword)}&remote_working_arrangement=1"
            try:
                html = fetch_page_html(
                    url,
                    ntfy_topic=self.ntfy_topic,
                    label=f"Bayt {country} ({keyword})",
                )
                all_jobs.extend(self._parse(html, keyword, country))
            except BlockedError:
                continue
            except Exception:
                continue
            time.sleep(1.5)
        return all_jobs

    def _parse(self, html: str, keyword: str, country: str) -> List[Job]:
        soup = BeautifulSoup(html, "html.parser")
        jobs: List[Job] = []
        # Bayt job cards: li.has-pointer-d or div.media within ul#results_inner_card
        cards = (
            soup.select("li.has-pointer-d")
            or soup.select("div[id^='jobItem_']")
            or soup.select("li.has-bottom-border")
        )
        seen_ids = set()
        for card in cards:
            title_el = card.select_one("h2, h2.is-bold a, [data-test='job-title']")
            company_el = card.select_one("b.jb-company, .t-default, [data-test='company-name']")
            loc_el = card.select_one(".t-mute, [data-test='location']")
            link_el = card.select_one("h2 a, a[data-js-aid='jobID']")
            sal_el = card.select_one(".jb-salary, [data-test='salary']")

            if not title_el or not company_el:
                continue
            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True)
            location = loc_el.get_text(strip=True) if loc_el else country
            href = link_el.get("href", "") if link_el else ""
            if href.startswith("/"):
                href = f"https://www.bayt.com{href}"

            jid = compute_job_id(title, company)
            if jid in seen_ids:
                continue
            seen_ids.add(jid)

            loc_with_country = (
                f"{location} — {country}" if country not in location else location
            )

            jobs.append(Job(
                job_id=jid,
                scraped_at=datetime.now(timezone.utc),
                posted_date=None,
                title=title,
                company=company,
                location=loc_with_country,
                remote_type="Remote",  # we filter ?remote_working_arrangement=1
                employment_type=None,
                salary_range=sal_el.get_text(strip=True) if sal_el else None,
                skills_tags=[country],
                keyword_matched=keyword,
                description_snippet="",
                source=self.NAME,
                url=href,
            ))
        return jobs
