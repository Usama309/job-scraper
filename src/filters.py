from __future__ import annotations

import hashlib
import re


_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def normalize(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def compute_job_id(title: str, company: str) -> str:
    """Deterministic 12-char hash from normalized title + company."""
    key = f"{normalize(title)}|{normalize(company)}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]


from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from src.models import Job


_REMOTE_KEYWORDS = ("remote", "anywhere", "wfh", "work from home", "fully remote")
_ONSITE_BLOCKERS = ("on-site", "onsite", "in-office", "hybrid")


def _parse_date(s: str) -> datetime | None:
    """Try ISO 8601, then RFC 2822, return UTC datetime or None."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    try:
        return parsedate_to_datetime(s).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def is_within_window(job: Job, hours: int) -> bool:
    """True if job posted_date is within last `hours`. Missing date = keep (True)."""
    if not job.posted_date:
        return True
    posted = _parse_date(job.posted_date)
    if posted is None:
        return True  # unparseable → keep, don't drop ambiguous data
    return (datetime.now(timezone.utc) - posted) <= timedelta(hours=hours)


def is_remote(job: Job) -> bool:
    """True if job location indicates remote."""
    loc = (job.location or "").lower()
    if any(b in loc for b in _ONSITE_BLOCKERS if "remote" not in loc):
        return False
    return any(k in loc for k in _REMOTE_KEYWORDS)


_SALARY_NUM_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def _parse_salary_to_monthly_usd(s: str) -> float | None:
    """Best-effort parse: detect /year /month /hour and return monthly USD floor."""
    if not s:
        return None
    nums = [float(n.replace(",", "")) for n in _SALARY_NUM_RE.findall(s)]
    if not nums:
        return None
    low = min(nums)
    low_lower = s.lower()
    if "hour" in low_lower or "/hr" in low_lower:
        return low * 160  # 40h/wk × 4wk
    if "month" in low_lower or "/mo" in low_lower:
        return low
    if "year" in low_lower or "/yr" in low_lower or "annum" in low_lower:
        return low / 12
    # No period marker: if number >= 1000 assume annual
    if low >= 1000:
        return low / 12
    return low * 160  # else treat as hourly


def meets_salary(job: Job, min_monthly_usd: float) -> bool:
    """True if salary is unlisted OR listed and >= min_monthly_usd."""
    if not job.salary_range:
        return True
    monthly = _parse_salary_to_monthly_usd(job.salary_range)
    if monthly is None:
        return True  # unparseable → keep
    return monthly >= min_monthly_usd
