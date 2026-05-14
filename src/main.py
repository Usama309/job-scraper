from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from src.filters import is_within_window, is_remote, meets_salary
from src.notify import NtfyClient
from src.sheets import SheetsClient


log = logging.getLogger("scraper")
ROOT = Path(__file__).parent.parent
CONFIG_DIR = ROOT / "config"

WINDOW_TO_HOURS = {"1h": 1, "6h": 6, "24h": 24, "3d": 72, "7d": 168, "30d": 720}

SCHEDULE_TO_SOURCES = {
    "hourly": ["remotive", "remoteok", "weworkremotely",
               "linkedin", "indeed", "glassdoor"],
    "6h":    ["adzuna"],
    "12h":   ["jsearch"],
    "all":   ["remotive", "remoteok", "weworkremotely", "adzuna", "jsearch",
              "linkedin", "indeed", "glassdoor"],
}


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--window", default="6h", choices=list(WINDOW_TO_HOURS))
    p.add_argument("--sources", default="hourly",
                   choices=list(SCHEDULE_TO_SOURCES))
    return p.parse_args(argv)


def load_keywords() -> list[str]:
    data = json.loads((CONFIG_DIR / "keywords.json").read_text())
    return [k for cat in data["categories"].values() for k in cat]


def load_filters() -> dict:
    return json.loads((CONFIG_DIR / "filters.json").read_text())


def _instantiate(name: str):
    if name == "remotive":
        from src.sources.remotive import RemotiveSource; return RemotiveSource()
    if name == "remoteok":
        from src.sources.remoteok import RemoteOKSource; return RemoteOKSource()
    if name == "weworkremotely":
        from src.sources.weworkremotely import WeWorkRemotelySource; return WeWorkRemotelySource()
    if name == "adzuna":
        from src.sources.adzuna import AdzunaSource; return AdzunaSource()
    if name == "jsearch":
        from src.sources.jsearch import JSearchSource; return JSearchSource()
    if name == "linkedin":
        from src.sources.linkedin import LinkedInSource; return LinkedInSource()
    if name == "indeed":
        from src.sources.indeed import IndeedSource; return IndeedSource()
    if name == "glassdoor":
        from src.sources.glassdoor import GlassdoorSource; return GlassdoorSource()
    raise ValueError(f"Unknown source: {name}")


def run(window: str, sources: str, trigger: str = "manual"):
    started = datetime.now(timezone.utc)
    t0 = time.time()
    hours = WINDOW_TO_HOURS[window]
    keywords = load_keywords()
    filters_cfg = load_filters()
    salary_floor = filters_cfg["salary"]["min_monthly_usd"]

    counts: dict[str, int] = {}
    errors: list[str] = []
    all_jobs = []

    for src_name in SCHEDULE_TO_SOURCES[sources]:
        try:
            src = _instantiate(src_name)
            if hasattr(src, "fetch_combined"):
                fetched = src.fetch_combined(keywords=keywords, time_window_hours=hours)
            else:
                fetched = []
                for kw in keywords:
                    fetched.extend(src.fetch(keyword=kw, time_window_hours=hours))
                    if hasattr(src, "http") and hasattr(src.http, "jitter"):
                        src.http.jitter(low=0.5, high=1.5)
            counts[src.NAME] = len(fetched)
            all_jobs.extend(fetched)
        except Exception as e:
            err = f"{src_name}: {type(e).__name__}: {e}"
            log.warning(err)
            errors.append(err)
            counts[src_name.title()] = 0

    # Filter
    filtered = [
        j for j in all_jobs
        if is_within_window(j, hours)
        and is_remote(j)
        and meets_salary(j, salary_floor)
    ]

    # Dedup by job_id
    by_id: dict[str, list] = {}
    for j in filtered:
        by_id.setdefault(j.job_id, []).append(j)
    deduped = [grp[0] for grp in by_id.values()]

    # Write to per-source tabs + master
    sheets_creds = json.loads(os.environ["GOOGLE_SHEETS_CREDS"])
    sheet_id = os.environ["GOOGLE_SHEET_ID"]
    sc = SheetsClient(creds=sheets_creds, sheet_id=sheet_id)
    sc.ensure_tabs()

    api_source_names = {"Remotive", "RemoteOK", "WeWorkRemotely", "Adzuna", "JSearch"}
    api_rows, li_rows, in_rows, gd_rows = [], [], [], []
    for j in filtered:
        row = j.to_sheet_row()
        if j.source in api_source_names:
            api_rows.append(row)
        elif j.source == "LinkedIn":
            li_rows.append(row)
        elif j.source == "Indeed":
            in_rows.append(row)
        elif j.source == "Glassdoor":
            gd_rows.append(row)
    sc.append_to_tab("API Sources", api_rows)
    sc.append_to_tab("LinkedIn", li_rows)
    sc.append_to_tab("Indeed", in_rows)
    sc.append_to_tab("Glassdoor", gd_rows)
    new_count, _ = sc.upsert_to_master(deduped)

    ended = datetime.now(timezone.utc)
    status = "Failed" if (errors and not deduped) else ("Partial" if errors else "OK")
    stats = {
        "started": started.strftime("%Y-%m-%d %H:%M UTC"),
        "ended": ended.strftime("%Y-%m-%d %H:%M UTC"),
        "duration_sec": int(time.time() - t0),
        "trigger": trigger,
        "time_window": window,
        "counts": counts,
        "after_dedup": len(deduped),
        "new_jobs": new_count,
        "errors": "; ".join(errors)[:500],
        "adzuna_quota": "",  # Phase 2 — read counter from sheet/file
        "jsearch_quota": "",
        "status": status,
    }
    sc.write_run_log(stats)

    body = (f"New: {new_count} | Deduped: {len(deduped)} | "
            + " ".join(f"{k}={v}" for k, v in counts.items()))
    priority = 5 if status == "Failed" else 3
    NtfyClient().send(title=f"Scraper {status}: {new_count} new jobs", body=body, priority=priority)
    return stats


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    args = parse_args()
    trigger = os.environ.get("GITHUB_EVENT_NAME", "manual")
    try:
        run(window=args.window, sources=args.sources, trigger=trigger)
    except Exception:
        traceback.print_exc()
        NtfyClient().send(title="Scraper CRASHED", body=traceback.format_exc()[-800:], priority=5)
        sys.exit(1)


if __name__ == "__main__":
    main()
