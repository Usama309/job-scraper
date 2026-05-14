# Project Scope — Job Scraper

_Last updated: 2026-05-13_

## Current State

The project is **fully built and tested (MVP complete)**. All 8 sources, the orchestration layer, Google Sheets integration, ntfy notifications, and 4 GitHub Actions workflows exist. All 44 unit tests pass.

### What Works

| Component | Status |
|-----------|--------|
| `src/main.py` — orchestration + filtering + dedup | Complete |
| `src/models.py` — Job dataclass + 26-col sheet serialization | Complete |
| `src/filters.py` — normalize, compute_job_id, is_within_window, is_remote, meets_salary | Complete |
| `src/sheets.py` — SheetsClient with upsert + run log | Complete |
| `src/notify.py` — NtfyClient | Complete |
| `src/sources/base.py` — HTTPClient (UA rotation, retry, jitter) | Complete |
| `src/sources/remotive.py` — Tier 1 JSON API | Complete |
| `src/sources/remoteok.py` — Tier 1 JSON API | Complete |
| `src/sources/weworkremotely.py` — Tier 1 RSS | Complete |
| `src/sources/adzuna.py` — Tier 1 keyed API (quota-limited) | Complete |
| `src/sources/jsearch.py` — Tier 1 RapidAPI | Complete |
| `src/sources/linkedin.py` — Tier 2 guest HTML | Complete |
| `src/sources/indeed.py` — Tier 2 RSS | Complete |
| `src/sources/glassdoor.py` — Tier 2 HTML (best-effort) | Complete |
| `.github/workflows/scrape-hourly.yml` | Complete |
| `.github/workflows/scrape-6h.yml` | Complete |
| `.github/workflows/scrape-12h.yml` | Complete |
| `.github/workflows/scrape-manual.yml` | Complete |
| `config/keywords.json` — ~40 keywords | Complete |
| `config/filters.json` — location + salary rules | Complete |
| `config/sources.json` — source metadata + quota limits | Complete |
| Test suite — 44 tests (models, filters, sources, sheets, notify) | Complete, all pass |
| Test fixtures — 8 files (json/html/rss per source) | Complete |

## In Progress

Nothing currently in progress.

## Architecture

### Data Flow

1. GitHub Actions triggers `main.py` with `--window` and `--sources` flags
2. `main.py` fans out to each source, collects `Job` dataclass instances
3. Filters applied: `is_within_window`, `is_remote`, `meets_salary`
4. Dedup by `job_id = sha256(normalize(title) + "|" + normalize(company))[:12]`
5. `SheetsClient.upsert_to_master()` — appends new jobs, updates Source Platforms column for existing, never touches V-Z
6. Per-source tab appends via `append_to_tab()`
7. `write_run_log()` writes 19-column audit row
8. `NtfyClient.send()` pushes summary to ClaudePilot ntfy channel

### Cron Schedule

| Workflow | Schedule | Sources | Quota reason |
|----------|----------|---------|--------------|
| scrape-hourly | 0 * * * * | Remotive, RemoteOK, WeWorkRemotely, LinkedIn, Indeed, Glassdoor | No quota |
| scrape-6h | 0 */6 * * * | Adzuna | 250 calls/month → 120/month at 4x/day |
| scrape-12h | 0 */12 * * * | JSearch | 150 calls/month → 60/month at 2x/day |
| scrape-manual | workflow_dispatch | All 8 sources | Operator choice |

### Sheet Structure

- `All Jobs` — master deduped tab, 26 columns (A-Z), columns V-Z are operator-owned
- `LinkedIn` — raw LinkedIn scraper output
- `Indeed` — raw Indeed RSS output
- `Glassdoor` — raw Glassdoor HTML output (may be empty due to Cloudflare)
- `API Sources` — all 5 API sources combined; column O (Primary Source) distinguishes them
- `Run Log` — 19-column audit trail per run

## Next Priorities

1. **Live credentials setup** — Usama needs to configure GitHub secrets:
   - `GOOGLE_SHEETS_CREDS`, `GOOGLE_SHEET_ID`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `RAPIDAPI_KEY`, `NTFY_TOPIC`
2. **First manual run** — trigger `scrape-manual.yml` with `24h` window to verify live behavior
3. **Push repo to GitHub** — push to `Usama309/job-scraper` to activate cron workflows

## Known Issues

See `.claude/KNOWN_ISSUES.md`

## Constraints

- Free-tier only — no paid scraping APIs
- Adzuna: 250 calls/month hard limit
- JSearch: 150 calls/month hard limit
- Glassdoor: Cloudflare blocks are expected; 0 results is acceptable
- LinkedIn guest API may rate-limit from GitHub Actions IPs over time
