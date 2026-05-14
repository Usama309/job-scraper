# Changelog — Job Scraper

All notable changes are documented here. Format: [YYYY-MM-DD HH:MM UTC] imperative tense.

## [Unreleased]

_Nothing pending since MVP completion._

---

## [1.0.0] — 2026-05-13

### Added

- [2026-05-13] Initial design spec v1 (3 HTML scrapers, 5-tab sheet)
- [2026-05-13] Design spec v2 — added 5 free-tier APIs, consolidated into API Sources tab, multi-rate cron
- [2026-05-13] `src/models.py` — Job dataclass with 26-column to_sheet_row() serialization
- [2026-05-13] `src/filters.py` — normalize, compute_job_id, is_within_window, is_remote, meets_salary
- [2026-05-13] `src/sources/base.py` — HTTPClient with rotating User-Agent, exponential backoff, jitter
- [2026-05-13] `src/sources/remotive.py` — Tier 1 JSON API source
- [2026-05-13] `src/sources/remoteok.py` — Tier 1 JSON API source
- [2026-05-13] `src/sources/weworkremotely.py` — Tier 1 RSS source (5 category feeds)
- [2026-05-13] `src/sources/adzuna.py` — Tier 1 keyed API with fetch_combined (quota-respecting)
- [2026-05-13] `src/sources/jsearch.py` — Tier 1 RapidAPI source with fetch_combined
- [2026-05-13] `src/sources/linkedin.py` — Tier 2 guest HTML scraper (3 pages per keyword)
- [2026-05-13] `src/sources/indeed.py` — Tier 2 RSS feed scraper
- [2026-05-13] `src/sources/glassdoor.py` — Tier 2 HTML scraper (best-effort, handles 403/Cloudflare)
- [2026-05-13] `src/sheets.py` — SheetsClient: ensure_tabs, append_to_tab, upsert_to_master (never overwrites V-Z), write_run_log
- [2026-05-13] `src/notify.py` — NtfyClient with priority, token auth support
- [2026-05-13] `src/main.py` — CLI orchestration with --window and --sources flags, SCHEDULE_TO_SOURCES map
- [2026-05-13] `config/keywords.json` — 40+ CRM/automation keywords across 4 categories
- [2026-05-13] `config/filters.json` — location include/exclude rules, $2500/mo salary floor
- [2026-05-13] `config/sources.json` — source-to-tab mapping with quota limits
- [2026-05-13] `.github/workflows/scrape-hourly.yml` — hourly cron for Tier 1 no-quota + Tier 2 sources
- [2026-05-13] `.github/workflows/scrape-6h.yml` — 6-hour cron for Adzuna
- [2026-05-13] `.github/workflows/scrape-12h.yml` — 12-hour cron for JSearch
- [2026-05-13] `.github/workflows/scrape-manual.yml` — workflow_dispatch with window selector, all 8 sources
- [2026-05-13] Full test suite — 44 tests covering models, filters, source parsing, sheets upsert, notify
- [2026-05-13] Test fixtures — 8 sample response files (JSON/HTML/RSS) for all sources
