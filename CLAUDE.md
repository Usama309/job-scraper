# Job Scraper — Claude Code Project Router

Inherits all rules from `~/.claude/CLAUDE.md`.

## Project Overview

Free-tier hybrid job scraper for remote positions. Pulls from 5 APIs (Remotive, RemoteOK, WeWorkRemotely, Adzuna, JSearch) + 3 HTML scrapers (LinkedIn, Indeed, Glassdoor), deduplicates by sha256(title+company), and writes to a 6-tab Google Sheet. Runs on GitHub Actions hourly/6h/12h cron + manual `workflow_dispatch`.

## Tech Stack

- Language: Python 3.11
- HTTP: `requests` with rotating User-Agent + exponential-backoff retry
- Parsing: `feedparser` (RSS), `beautifulsoup4` (HTML)
- Storage: Google Sheets via `gspread` + service account
- Notifications: ntfy (ClaudePilot channel)
- CI: GitHub Actions (`ubuntu-latest` — US IP, solves geolocation problem)

## Key Files

- `src/main.py` — CLI entry point, orchestration, filtering, dedup, write loop
- `src/models.py` — `Job` dataclass + `to_sheet_row()` (26 columns A-Z)
- `src/filters.py` — `normalize`, `compute_job_id`, `is_within_window`, `is_remote`, `meets_salary`
- `src/sheets.py` — `SheetsClient`: `ensure_tabs`, `append_to_tab`, `upsert_to_master`, `write_run_log`
- `src/notify.py` — `NtfyClient`
- `src/sources/base.py` — `HTTPClient` with UA rotation, retry, jitter
- `src/sources/*.py` — one file per source (remotive, remoteok, weworkremotely, adzuna, jsearch, linkedin, indeed, glassdoor)
- `config/keywords.json` — ~40 search keywords (user-editable)
- `config/filters.json` — location rules, salary floor ($2500/mo)
- `config/sources.json` — source-to-tab + quota metadata
- `.github/workflows/` — 4 workflow files

## Project Governance

- Spec: `docs/superpowers/specs/2026-05-13-job-scraper-design.md`
- Plan: `docs/superpowers/plans/2026-05-13-job-scraper.md`
- Scope: `.claude/PROJECT_SCOPE.md`
- Changelog: `.claude/CHANGELOG.md`
- Tasks: `.claude/TASKLIST.md`
- Decisions: `.claude/DECISIONS.md`
- Known Issues: `.claude/KNOWN_ISSUES.md`

## Critical Rules

- Operator columns V-Z on the `All Jobs` sheet tab are NEVER overwritten by scraper logic — this is enforced in `upsert_to_master` and covered by a unit test
- Adzuna is capped at 250 calls/month; JSearch at 150 calls/month — never move them to the hourly schedule
- Run `source .venv/bin/activate && python -m pytest` to verify tests (44 tests, all pass)
- Glassdoor may return 0 results (Cloudflare blocks) — this is expected and handled
