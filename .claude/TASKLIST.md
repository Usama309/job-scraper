# Task List — Job Scraper

_Last updated: 2026-05-13_

## Summary

- Completed: 13 tasks
- In Progress: 0
- Pending: 4

---

## Completed Tasks

- [x] Scaffold repo structure (src/, config/, tests/, .github/workflows/) (completed 2026-05-13)
- [x] Write `requirements.txt` with all dependencies (completed 2026-05-13)
- [x] Write `README.md` with local dev + secrets documentation (completed 2026-05-13)
- [x] Build `src/models.py` — Job dataclass + 26-column to_sheet_row() (completed 2026-05-13)
- [x] Build `src/filters.py` — normalize, compute_job_id, is_within_window, is_remote, meets_salary (completed 2026-05-13)
- [x] Build `src/sources/base.py` — HTTPClient with UA rotation, exponential retry, jitter (completed 2026-05-13)
- [x] Build all 8 source modules (remotive, remoteok, weworkremotely, adzuna, jsearch, linkedin, indeed, glassdoor) (completed 2026-05-13)
- [x] Build `src/sheets.py` — SheetsClient with ensure_tabs, append_to_tab, upsert_to_master (preserves V-Z), write_run_log (completed 2026-05-13)
- [x] Build `src/notify.py` — NtfyClient with topic/token from env (completed 2026-05-13)
- [x] Build `src/main.py` — CLI entry, orchestration, filtering, dedup, sheet write loop (completed 2026-05-13)
- [x] Create `config/keywords.json` with ~40 CRM/automation keywords (completed 2026-05-13)
- [x] Create `config/filters.json` with location rules + salary floor ($2500/mo) (completed 2026-05-13)
- [x] Create `config/sources.json` with source metadata + quota limits (completed 2026-05-13)
- [x] Write 4 GitHub Actions workflow files (hourly, 6h, 12h, manual) (completed 2026-05-13)
- [x] Write complete test suite — 44 tests across models, filters, sources, sheets, notify (completed 2026-05-13)
- [x] Create test fixtures for all 8 sources (json/html/rss) (completed 2026-05-13)
- [x] Verify all 44 tests pass (completed 2026-05-13)

---

## Pending Tasks

- [ ] Set up Google Cloud service account + enable Sheets/Drive APIs (Usama, one-time)
- [ ] Sign up for Adzuna developer account and get app_id + app_key (Usama, one-time)
- [ ] Sign up for RapidAPI and subscribe to JSearch free plan (Usama, one-time)
- [ ] Add all 6 GitHub Actions secrets to `Usama309/job-scraper` repo
- [ ] Push repo to GitHub (`Usama309/job-scraper`) to activate cron workflows
- [ ] Run first manual trigger (`scrape-manual.yml`, window=24h) and verify sheet output
- [ ] Verify Run Log row is written with all 19 columns populated
- [ ] Verify ntfy push received in ClaudePilot channel
- [ ] Verify dedup: run same window twice, confirm no duplicate rows

---

## Phase 2 Backlog (Out of Scope for v1)

- [ ] ClaudePilot dashboard "Run Scraper" button + "Recent Runs" widget
- [ ] Job analyzer integration — fill column L (Match Score) from CV scoring
- [ ] Auto-prune rows older than 30 days from All Jobs tab
- [ ] Playwright fallback for Glassdoor / rate-limited LinkedIn
- [ ] Salary normalization — parse multi-format salaries into monthly USD
- [ ] Jobright source integration
- [ ] Geographic split — US-remote vs international-remote tabs
