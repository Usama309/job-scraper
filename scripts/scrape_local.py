#!/usr/bin/env python3
"""Local-execution Indeed + Glassdoor scraper.

Runs on your Mac via Comet (CDP on localhost:9222). Real Chrome = real cookies
+ real TLS fingerprint, bypassing the 403s that hit GitHub Actions.

When Cloudflare/captcha appears, sends ntfy push to your iPhone and polls
every 8s until you solve it in the visible Comet window. Then continues.

Usage:
    python scripts/scrape_local.py --window 24h --sources both
    python scripts/scrape_local.py --window 7d --sources indeed
"""
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

# Make src/ importable when run from project root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env if present so manual runs pick up secrets
ENV_FILE = ROOT / ".env"
if ENV_FILE.exists():
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from src.comet_client import ensure_comet_running, CometUnavailableError, BlockedError  # noqa: E402
from src.filters import is_within_window, is_remote, meets_salary  # noqa: E402
from src.main import WINDOW_TO_HOURS, load_keywords, load_filters  # noqa: E402
from src.notify import NtfyClient  # noqa: E402
from src.sheets import SheetsClient  # noqa: E402
from src.sources.bayt_browser import BaytBrowserSource  # noqa: E402
from src.sources.glassdoor_browser import GlassdoorBrowserSource  # noqa: E402
from src.sources.indeed_browser import IndeedBrowserSource  # noqa: E402


log = logging.getLogger("scrape_local")

ALL_SOURCES = ["indeed", "glassdoor", "bayt"]


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--window", default="24h", choices=list(WINDOW_TO_HOURS))
    p.add_argument("--sources", default="all",
                   choices=["all", "indeed", "glassdoor", "bayt"])
    p.add_argument("--max-keywords", type=int, default=8,
                   help="Cap keyword count (multi-country runs scale O(keywords × countries)). Default 8.")
    return p.parse_args(argv)


def _instantiate(name: str):
    if name == "indeed":
        return IndeedBrowserSource()
    if name == "glassdoor":
        return GlassdoorBrowserSource()
    if name == "bayt":
        return BaytBrowserSource()
    raise ValueError(name)


def run(window: str, sources_choice: str, max_keywords: int) -> dict:
    started = datetime.now(timezone.utc)
    t0 = time.time()
    hours = WINDOW_TO_HOURS[window]
    keywords = load_keywords()[:max_keywords]
    filters_cfg = load_filters()
    salary_floor = filters_cfg["salary"]["min_monthly_usd"]

    source_names = ALL_SOURCES if sources_choice == "all" else [sources_choice]
    counts: dict[str, int] = {}
    errors: list[str] = []
    all_jobs = []

    for src_name in source_names:
        try:
            src = _instantiate(src_name)
            fetched = []
            for kw in keywords:
                try:
                    fetched.extend(src.fetch(keyword=kw, time_window_hours=hours))
                except BlockedError as be:
                    errors.append(f"{src_name}/{kw}: {be}")
                    log.warning(f"{src_name}/{kw} BLOCKED: {be}")
                except Exception as e:
                    errors.append(f"{src_name}/{kw}: {type(e).__name__}: {e}")
                    log.warning(f"{src_name}/{kw} error: {e}")
                time.sleep(2)  # gentle pacing between Comet tabs
            counts[src.NAME] = len(fetched)
            all_jobs.extend(fetched)
        except Exception as e:
            err = f"{src_name}: {type(e).__name__}: {e}"
            log.warning(err)
            errors.append(err)
            counts[src_name.title()] = 0

    filtered = [
        j for j in all_jobs
        if is_within_window(j, hours)
        and is_remote(j)
        and meets_salary(j, salary_floor)
    ]
    by_id: dict[str, list] = {}
    for j in filtered:
        by_id.setdefault(j.job_id, []).append(j)
    deduped = [grp[0] for grp in by_id.values()]

    creds = json.loads(os.environ["GOOGLE_SHEETS_CREDS"])
    sc = SheetsClient(creds=creds, sheet_id=os.environ["GOOGLE_SHEET_ID"])
    sc.ensure_tabs()

    in_rows, gd_rows, api_rows = [], [], []
    for j in filtered:
        row = j.to_sheet_row()
        if j.source == "Indeed":
            in_rows.append(row)
        elif j.source == "Glassdoor":
            gd_rows.append(row)
        elif j.source == "Bayt":
            # Bayt is a regional aggregator — group with API Sources tab
            api_rows.append(row)
    sc.append_to_tab("Indeed", in_rows)
    sc.append_to_tab("Glassdoor", gd_rows)
    sc.append_to_tab("API Sources", api_rows)
    new_count, _ = sc.upsert_to_master(deduped)

    ended = datetime.now(timezone.utc)
    status = "Failed" if (errors and not deduped) else ("Partial" if errors else "OK")
    stats = {
        "started": started.strftime("%Y-%m-%d %H:%M UTC"),
        "ended": ended.strftime("%Y-%m-%d %H:%M UTC"),
        "duration_sec": int(time.time() - t0),
        "trigger": "local",
        "time_window": window,
        "counts": counts,
        "after_dedup": len(deduped),
        "new_jobs": new_count,
        "errors": "; ".join(errors)[:500],
        "adzuna_quota": "",
        "jsearch_quota": "",
        "status": status,
    }
    sc.write_run_log(stats)

    body = (f"Local scrape: {new_count} new | dedup {len(deduped)} | "
            + " ".join(f"{k}={v}" for k, v in counts.items()))
    priority = 5 if status == "Failed" else 3
    NtfyClient().send(title=f"Local Scraper {status}", body=body, priority=priority)
    return stats


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    args = parse_args()
    try:
        ensure_comet_running()
    except CometUnavailableError as e:
        print(f"\nERROR: {e}\n", file=sys.stderr)
        print("Start Comet first. Example:\n"
              '  open -na "Comet" --args --remote-debugging-port=9222 \\\n'
              '    --user-data-dir="$HOME/Library/Application Support/Comet"\n',
              file=sys.stderr)
        sys.exit(2)
    try:
        stats = run(window=args.window, sources_choice=args.sources, max_keywords=args.max_keywords)
        print(json.dumps(stats, indent=2))
    except Exception:
        traceback.print_exc()
        try:
            NtfyClient().send(title="Local Scraper CRASHED",
                              body=traceback.format_exc()[-800:], priority=5)
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
