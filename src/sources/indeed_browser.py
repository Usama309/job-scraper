"""Indeed scraper that runs through Comet (real Chrome) instead of direct HTTP.

Use this from `scripts/scrape_local.py` only — it requires Comet running with
CDP enabled on localhost:9222. The regular `indeed.py` is HTTP-based and gets
403'd from datacenter/Pakistan IPs.

Multi-country: rotates through Indeed's country subdomains (uk.indeed.com,
de.indeed.com, ae.indeed.com, etc.) per the config/countries.json file.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from src.comet_client import BlockedError, fetch_page_html
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


def _load_countries() -> dict:
    cfg = Path(__file__).resolve().parent.parent.parent / "config" / "countries.json"
    return json.loads(cfg.read_text())


class IndeedBrowserSource:
    NAME = "Indeed"

    def __init__(self):
        self.ntfy_topic = os.environ.get("NTFY_TOPIC", "")
        self.countries = _load_countries()["indeed_domains"]

    def fetch(self, *, keyword: str, time_window_hours: int) -> List[Job]:
        fromage = _hours_to_fromage(time_window_hours)
        all_jobs: List[Job] = []
        for country, domain in self.countries.items():
            url = (
                f"https://{domain}/jobs?q={quote_plus(keyword)}"
                f"&l=Remote&fromage={fromage}&sort=date"
            )
            try:
                html = fetch_page_html(
                    url,
                    ntfy_topic=self.ntfy_topic,
                    label=f"Indeed {country} ({keyword})",
                )
                all_jobs.extend(self._parse(html, keyword, country))
            except BlockedError:
                # CAPTCHA timeout — keep going to the next country
                continue
            except Exception:
                continue
            time.sleep(1.5)  # gentle pacing between countries
        return all_jobs

    def _parse(self, html: str, keyword: str, country: str = "") -> List[Job]:
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
            desc_el = card.select_one("[data-testid='jobsnippet_footer'], div.job-snippet, ul li")

            if not title_el or not company_el:
                continue
            title = title_el.get_text(strip=True)
            company = company_el.get_text(strip=True)
            location = (loc_el.get_text(strip=True) if loc_el else "") or "Remote"
            desc = desc_el.get_text(" ", strip=True) if desc_el else ""
            # "Loose remote": accept if title/desc says remote even if location is a city
            loose_remote = (
                "remote" in title.lower()
                or "remote" in location.lower()
                or "remote" in desc.lower()
            )
            href = link_el.get("href", "") if link_el else ""
            if href and href.startswith("/"):
                # Country-aware absolute URL (preserves subdomain so links work)
                domain = self.countries.get(country, "www.indeed.com")
                href = f"https://{domain}{href}"
            elif not href and jk:
                domain = self.countries.get(country, "www.indeed.com")
                href = f"https://{domain}/viewjob?jk={jk}"

            jid = compute_job_id(title, company)
            if jid in seen_ids:
                continue
            seen_ids.add(jid)
            # Tag the country in location so downstream filters/operators can see it
            loc_with_country = (
                f"{location} — {country}" if country and country not in location else location
            )

            jobs.append(Job(
                job_id=jid,
                scraped_at=datetime.now(timezone.utc),
                posted_date=posted_el.get_text(strip=True) if posted_el else None,
                title=title,
                company=company,
                location=loc_with_country,
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
