# Job Scraper — Design Spec

**Author:** Muhammad Usama
**Date:** 2026-05-13
**Status:** Design v2 — APIs added per user request; awaiting re-approval before implementation plan
**Owner repo (planned):** `Usama309/job-scraper`

---

## Changelog

- **v1 (2026-05-13)** — Initial spec with 3 HTML scrapers (LinkedIn, Indeed, Glassdoor) → 5-tab sheet
- **v2 (2026-05-13)** — Added 5 free-tier APIs (Remotive, RemoteOK, WeWorkRemotely, Adzuna, JSearch). Consolidated all API output into one new `API Sources` tab → 6-tab sheet. Introduced multi-rate cron (hourly + 6h + 12h) to respect API quotas.

---

## 1. Problem Statement

Usama (Pakistan-based, currently job-hunting) hired an operator in Pakistan to apply for remote US jobs on his behalf. The operator's Pakistan IP causes LinkedIn, Indeed, and Glassdoor to geolocate the operator to Pakistan and surface mostly Pakistan-region jobs, not US-remote roles. This wastes operator hours and misses relevant opportunities.

Usama needs a scraper that:
- Runs hourly, unattended
- Has a manual "run now" trigger
- Pulls job postings from **LinkedIn**, **Indeed**, **Glassdoor** plus **5 free-tier job APIs** for redundancy and coverage
- Returns **remote jobs (any country)** matching his CV-derived keyword set
- Writes results to a Google Sheet, separated by source category + one master deduped tab
- Free-tier only — no paid scraping APIs in v1
- Eventually integrates into his existing ClaudePilot platform (Phase 2)

The scraped sheet feeds an existing job analyzer that scores each posting against Usama's CV.

---

## 2. Goals

- **G1.** Hourly automated scrape + manual on-demand trigger
- **G2.** Configurable time window per run: `1h | 6h | 24h | 3d | 7d | 30d` (default `6h` for cron)
- **G3.** US-IP-sourced requests (no Pakistan-IP geolocation pollution) via GitHub Actions
- **G4.** All free-tier — zero per-month spend
- **G5.** Six-tab Google Sheet output: `All Jobs`, `LinkedIn`, `Indeed`, `Glassdoor`, `API Sources`, `Run Log`
- **G6.** Deterministic deduplication across all sources via `Job ID` hash
- **G7.** Operator-editable status/notes columns are preserved across re-scrapes
- **G8.** Push notification (ntfy) on every run completion with summary or error
- **G9.** Hybrid sourcing: 5 reliable APIs (Tier 1) + 3 best-effort HTML scrapers (Tier 2)
- **G10.** Respect API quotas via multi-rate cron — never blow free tier limits

## Non-Goals (v1)

- Paid scraping APIs (ScraperAPI, Apify, etc.)
- ClaudePilot dashboard button (Phase 2)
- Salary normalization across currencies/periods
- Auto-pruning of old sheet rows
- Match Score calculation (filled later by existing analyzer)
- Resume tailoring / auto-apply
- Jobright source

---

## 3. Architecture

### 3.1 High-level data flow

```
┌────────────────────────────────────────────────────────────────────┐
│ GitHub Actions (US-based runners)                                  │
│                                                                    │
│  Three cron schedules:                                             │
│    A.  '0 * * * *'    → hourly: hourly_run()                       │
│    B.  '0 */6 * * *'  → every 6h: medium_run()                     │
│    C.  '0 */12 * * *' → every 12h: heavy_run()                     │
│  Plus: workflow_dispatch (manual button, runs all sources)         │
│                                                                    │
│  ┌──────────────────────────────────────────────────────┐          │
│  │ TIER 1 — APIs (reliable, structured)                 │          │
│  │  Hourly:    Remotive, RemoteOK, WeWorkRemotely       │          │
│  │  Every 6h:  Adzuna       (250/month quota)           │          │
│  │  Every 12h: JSearch      (150/month quota)           │          │
│  └─────────────────────┬────────────────────────────────┘          │
│                        │                                           │
│  ┌─────────────────────┴────────────────────────────────┐          │
│  │ TIER 2 — HTML/RSS scrapers (best-effort)             │          │
│  │  Hourly:    LinkedIn (guest API), Indeed (RSS),      │          │
│  │             Glassdoor (HTML, may yield 0)            │          │
│  └─────────────────────┬────────────────────────────────┘          │
│                        ▼                                           │
│           ┌─────────────────────────────────────┐                  │
│           │ Filter → Dedup → Merge              │                  │
│           │  • time_window cutoff               │                  │
│           │  • location contains "remote"       │                  │
│           │  • salary ≥ $2500/mo if listed      │                  │
│           │  • Job ID = sha256(title+company)   │                  │
│           └─────────────────┬───────────────────┘                  │
└─────────────────────────────┼──────────────────────────────────────┘
                              ▼
            ┌─────────────────────────────────────┐
            │ Google Sheets API (service account) │
            │                                     │
            │  • Append new jobs                  │
            │  • Update existing on Source change │
            │  • Preserve operator columns (V-Z)  │
            │  • Write Run Log row                │
            └────────────────┬────────────────────┘
                             ▼
                    ┌────────────────┐
                    │ ntfy push      │
                    │ to ClaudePilot │
                    │ channel        │
                    └────────────────┘
```

### 3.2 Hosting: GitHub Actions

**Why GitHub Actions instead of Hostinger VPS:**
- US-based runners by default → solves geolocation problem at zero cost
- 2,000 free minutes/month — sufficient for hourly + 6h + 12h workflows combined
- Built-in cron + `workflow_dispatch` (the "manual button")
- Logs, retries, secrets management — all free
- Decoupled from Hostinger VPS (which may be in non-US region)

**Runner type:** `ubuntu-latest`

**Workflows:**

| Workflow file | Schedule | Sources run |
|---------------|----------|-------------|
| `scrape-hourly.yml` | `0 * * * *` | Remotive, RemoteOK, WeWorkRemotely, LinkedIn, Indeed, Glassdoor |
| `scrape-6h.yml` | `0 */6 * * *` | Adzuna only (1 OR-query call) |
| `scrape-12h.yml` | `0 */12 * * *` | JSearch only (1 query call) |
| `scrape-manual.yml` | `workflow_dispatch` | **All 8 sources** with chosen time window |

Manual trigger uses **all** sources regardless of quota — operator's choice. After a manual run, the next 6h/12h cron may be skipped if quota is tight (logged in Run Log).

### 3.3 Repo structure (`Usama309/job-scraper`)

```
job-scraper/
├── .github/
│   └── workflows/
│       ├── scrape-hourly.yml       # Tier 1+2 fast sources
│       ├── scrape-6h.yml           # Adzuna only
│       ├── scrape-12h.yml          # JSearch only
│       └── scrape-manual.yml       # all sources, on-demand
├── src/
│   ├── __init__.py
│   ├── main.py                     # entry point — accepts --sources flag
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py                 # shared HTTP, retry, throttle, UA rotation
│   │   ├── linkedin.py             # Tier 2 — guest API HTML scrape
│   │   ├── indeed.py               # Tier 2 — RSS feed
│   │   ├── glassdoor.py            # Tier 2 — HTML scrape (best-effort)
│   │   ├── remotive.py             # Tier 1 — public JSON API
│   │   ├── remoteok.py             # Tier 1 — public JSON API
│   │   ├── weworkremotely.py       # Tier 1 — RSS feed
│   │   ├── adzuna.py               # Tier 1 — keyed JSON API
│   │   └── jsearch.py              # Tier 1 — RapidAPI JSON
│   ├── filters.py                  # time / location / salary / dedup logic
│   ├── sheets.py                   # gspread wrapper
│   ├── notify.py                   # ntfy push client
│   └── models.py                   # Job dataclass
├── config/
│   ├── keywords.json               # ~40 search keywords (user-editable)
│   ├── filters.json                # location rules, salary floor, exclusions
│   └── sources.json                # source-to-tab mapping, quota tracking
├── tests/
│   ├── test_filters.py
│   ├── test_dedup.py
│   ├── test_sources_parsing.py
│   └── fixtures/                   # sample JSON/HTML/RSS for offline testing
├── requirements.txt
├── README.md
├── .gitignore                      # excludes credentials.json, .env
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-05-13-job-scraper-design.md  # this file
```

### 3.4 Components

**`src/sources/base.py`** — shared HTTP behavior for all 8 sources:
- `requests.Session` with rotating User-Agent (5–10 modern desktop browsers)
- Exponential-backoff retry: 3 attempts at 1s, 3s, 9s
- 2–5 second jitter between requests within same source
- Timeout: 15s per request
- Returns parsed `Job` dataclass instances
- Each source class implements `fetch(keyword: str, time_window_hours: int) -> list[Job]`

#### Tier 1 — APIs

**`remotive.py`** — Remotive public API
- Endpoint: `https://remotive.com/api/remote-jobs?search=<kw>`
- No auth. Unlimited rate.
- Returns JSON with structured fields (title, company, location, tags, salary, date)
- Filter `publication_date` against time window post-fetch

**`remoteok.py`** — RemoteOK public API
- Endpoint: `https://remoteok.com/api?tags=<kw>` (or full feed without tags)
- No auth. Unlimited rate.
- Returns JSON list. First element is metadata; rest are jobs
- Filter `date` field against time window post-fetch
- Required: `User-Agent` header (RemoteOK blocks generic Python UA)

**`weworkremotely.py`** — WeWorkRemotely RSS
- Endpoint: `https://weworkremotely.com/categories/<category>/jobs.rss`
- Categories: `remote-programming-jobs`, `remote-customer-support-jobs`, `remote-sales-and-marketing-jobs`, `remote-product-jobs`, `remote-design-jobs`
- No auth. Unlimited rate.
- Parse with `feedparser`. Filter `published` against time window

**`adzuna.py`** — Adzuna API (keyed, quota-limited)
- Endpoint: `https://api.adzuna.com/v1/api/jobs/us/search/1`
- Auth: `app_id` + `app_key` (free signup at developer.adzuna.com)
- Quota: **250 calls/month** free → strict budget enforcement
- Strategy: ONE call per run using `what_or="GoHighLevel HubSpot Zapier n8n ..."` (all keywords as OR query, up to 50 results per call)
- Run frequency: **every 6 hours** (4×/day × 30 = 120 calls/month, under quota)
- Adds buffer for manual runs

**`jsearch.py`** — JSearch via RapidAPI
- Endpoint: `https://jsearch.p.rapidapi.com/search?query=<kw>&page=1`
- Auth: `X-RapidAPI-Key` header (free signup at rapidapi.com)
- Quota: **150 calls/month** free → strictest budget
- Aggregates **LinkedIn + Indeed + Glassdoor + ZipRecruiter** — single most valuable API
- Strategy: ONE broad call per run with combined query
- Run frequency: **every 12 hours** (2×/day × 30 = 60 calls/month, under quota)
- Result's `apply_options[*].publisher` tells us original source (LinkedIn/Indeed/etc.)

#### Tier 2 — HTML/RSS scrapers (best-effort)

**`linkedin.py`** — LinkedIn guest job-search
- Endpoint: `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search`
- Params: `keywords=<kw>`, `location=Worldwide`, `f_TPR=r<seconds>`, `f_WT=2` (remote), `start=0..N`
- Returns HTML chunks → parse with BeautifulSoup
- Iterate `start=0, 25, 50` (up to 75 jobs) per keyword

**`indeed.py`** — Indeed RSS
- Endpoint: `https://www.indeed.com/rss?q=<kw>&l=remote&fromage=<days>&sort=date`
- `fromage` mapping: `1h/6h/24h → 1`, `3d → 3`, `7d → 7`, `30d → 30`
- Parse with `feedparser`. Filter post-scrape using item pubDate for sub-day windows

**`glassdoor.py`** — Glassdoor best-effort
- Endpoint: `https://www.glassdoor.com/Job/remote-<kw>-jobs-SRCH_IL.0,6_IS11047_KO7,<n>.htm`
- HTML scrape with BeautifulSoup
- Cloudflare-protected — wrap in try/except, log failures, never block others
- v1: accept 0 results; v2 may add Playwright fallback

**`src/filters.py`** — post-scrape filtering:
- `is_within_window(job, hours)` — drops jobs older than window
- `is_remote(job)` — accepts location containing `remote`, `anywhere`, `wfh`, `work from home`
- `meets_salary(job, min_monthly_usd=2500)` — drops jobs with **listed** salary below floor; keeps jobs with no salary listed
- `compute_job_id(job)` — `sha256(normalize(title) + "|" + normalize(company))[:12]`
- `normalize(s)` — lowercase, strip, collapse whitespace, remove punctuation

**`src/sheets.py`** — Google Sheets I/O:
- Auth via service account JSON from env var `GOOGLE_SHEETS_CREDS`
- Sheet ID from env var `GOOGLE_SHEET_ID`
- `append_to_tab(tab_name, rows)` — appends rows
- `upsert_to_master(jobs)` — checks Job ID against existing; appends if new, updates `Source Platforms` column if seen on additional source; **never overwrites columns V–Z** (operator-owned)
- `write_run_log(stats)` — appends one row to Run Log tab

**`src/notify.py`** — ntfy push:
- POST to `https://ntfy.sh/<NTFY_TOPIC>` (or self-hosted endpoint)
- Title: `Scraper: <total> new jobs`
- Body: per-source breakdown + duration + error summary if any
- Priority `5` (max + bell) if **all** sources failed; priority `3` (default) otherwise

---

## 4. Data Model

### 4.1 `Job` dataclass

```python
@dataclass
class Job:
    job_id: str               # sha256(title+company)[:12]
    scraped_at: datetime
    posted_date: str | None
    title: str
    company: str
    location: str
    remote_type: str | None      # "Remote" | "Hybrid" | "On-site"
    employment_type: str | None
    salary_range: str | None
    skills_tags: list[str]
    keyword_matched: str
    description_snippet: str     # first 300 chars
    source: str                  # "LinkedIn" | "Indeed" | "Glassdoor"
                                 # | "Remotive" | "RemoteOK"
                                 # | "WeWorkRemotely" | "Adzuna" | "JSearch"
    url: str
    company_website: str | None
    recruiter_name: str | None
    recruiter_contact: str | None
```

### 4.2 Google Sheet structure — 6 tabs

#### Tab 1: `All Jobs` (master, deduped) — 26 columns (A→Z)

| Col | Field | Source |
|-----|-------|--------|
| A | Job ID | auto |
| B | Scraped At | auto |
| C | Posted Date | scraped |
| D | Job Title | scraped |
| E | Company Name | scraped |
| F | Location | scraped |
| G | Remote Type | derived |
| H | Employment Type | scraped |
| I | Salary Range | scraped |
| J | Skills / Tags | scraped |
| K | Keyword Matched | auto |
| L | Match Score | analyzer (later) |
| M | Description Snippet | scraped |
| N | Source Platforms | auto (all 8 possible) |
| O | Primary Source | auto (first surfacer) |
| P | LinkedIn URL | scraped |
| Q | Indeed URL | scraped |
| R | Glassdoor URL | scraped |
| S | Company Website | scraped |
| T | Recruiter Name | scraped |
| U | Recruiter Contact | scraped/manual |
| V | Application Status | **manual** |
| W | Applied On | **manual** |
| X | Follow-up Date | **manual** |
| Y | Resume Version Used | **manual** |
| Z | Notes | **manual** |

**Upsert rule:** If Job ID already exists, only update columns A–U; never touch V–Z.

**Source Platforms column N** can hold values like: `LinkedIn`, `Indeed, JSearch (LinkedIn)`, `Remotive, RemoteOK, WeWorkRemotely`, etc.

For API sources, format is `<API> (<underlying publisher>)` when known — e.g., `JSearch (LinkedIn)` means JSearch returned a job originally posted on LinkedIn. For Remotive/RemoteOK/WWR, just the API name.

#### Tabs 2–4: `LinkedIn`, `Indeed`, `Glassdoor` (raw HTML scraper output)

Same 26-column structure. Each tab only contains rows surfaced by that specific HTML scraper. Operator columns (V–Z) and cross-source columns (N, O) stay blank — those only have meaning on the master tab.

#### Tab 5: `API Sources` (all 5 APIs grouped)

Same 26-column structure with one key difference: the `Primary Source` column (O) is **mandatory** on this tab and holds the API name (`Remotive` / `RemoteOK` / `WeWorkRemotely` / `Adzuna` / `JSearch`). For `JSearch`, also captures the underlying publisher in parentheses where available.

Filter the tab by column O to see results from a single API.

#### Tab 6: `Run Log` (audit trail) — extended

| Col | Field |
|-----|-------|
| A | Run Started (UTC) |
| B | Run Ended (UTC) |
| C | Duration (sec) |
| D | Trigger (`hourly` / `6h` / `12h` / `manual`) |
| E | Time Window |
| F | LinkedIn Found |
| G | Indeed Found |
| H | Glassdoor Found |
| I | Remotive Found |
| J | RemoteOK Found |
| K | WeWorkRemotely Found |
| L | Adzuna Found |
| M | JSearch Found |
| N | After Dedup |
| O | New Jobs (not seen before) |
| P | Errors |
| Q | Adzuna Quota Used | `42 / 250` |
| R | JSearch Quota Used | `18 / 150` |
| S | Status (`OK` / `Partial` / `Failed`) |

---

## 5. Configuration

### 5.1 `config/keywords.json` — same as v1 (~40 keywords, user-editable)

### 5.2 `config/filters.json` — same as v1

### 5.3 `config/sources.json` — NEW

Controls which sources run on which schedule, and tracks quota state.

```json
{
  "sources": {
    "remotive":       { "tier": 1, "schedule": "hourly", "quota_monthly": null, "tab": "API Sources" },
    "remoteok":       { "tier": 1, "schedule": "hourly", "quota_monthly": null, "tab": "API Sources" },
    "weworkremotely": { "tier": 1, "schedule": "hourly", "quota_monthly": null, "tab": "API Sources" },
    "adzuna":         { "tier": 1, "schedule": "6h",     "quota_monthly": 250,  "tab": "API Sources" },
    "jsearch":        { "tier": 1, "schedule": "12h",    "quota_monthly": 150,  "tab": "API Sources" },
    "linkedin":       { "tier": 2, "schedule": "hourly", "quota_monthly": null, "tab": "LinkedIn" },
    "indeed":         { "tier": 2, "schedule": "hourly", "quota_monthly": null, "tab": "Indeed" },
    "glassdoor":      { "tier": 2, "schedule": "hourly", "quota_monthly": null, "tab": "Glassdoor" }
  }
}
```

---

## 6. Setup & Credentials

### 6.1 One-time external account setup (Usama performs)

1. **Google Cloud:**
   - Create project (free)
   - Enable Sheets API + Drive API
   - Create service account, download `credentials.json`
   - Create Google Sheet named `Job Scraper`
   - Share sheet with service account email as **Editor**

2. **Adzuna** (free, ~5 min):
   - Sign up at https://developer.adzuna.com/signup
   - Get `app_id` and `app_key`

3. **RapidAPI / JSearch** (free, ~5 min):
   - Sign up at https://rapidapi.com
   - Subscribe to JSearch's free plan (150 req/month)
   - Copy `X-RapidAPI-Key`

4. **ntfy** (already set up via ClaudePilot)

### 6.2 GitHub Actions secrets

| Secret | Value | Purpose |
|--------|-------|---------|
| `GOOGLE_SHEETS_CREDS` | full JSON of `credentials.json` | Sheets API auth |
| `GOOGLE_SHEET_ID` | sheet URL ID | Tells script which sheet |
| `ADZUNA_APP_ID` | from Adzuna signup | Adzuna API auth |
| `ADZUNA_APP_KEY` | from Adzuna signup | Adzuna API auth |
| `RAPIDAPI_KEY` | from RapidAPI signup | JSearch API auth |
| `NTFY_TOPIC` | ClaudePilot ntfy topic | Push notifications |
| `NTFY_TOKEN` | (optional) | If ntfy auth required |

No LinkedIn/Indeed/Glassdoor credentials needed — Tier 2 uses public endpoints. Remotive/RemoteOK/WeWorkRemotely also need no auth.

---

## 7. Failure Handling

| Failure mode | Behavior |
|--------------|----------|
| Single source throws | Caught, logged in Run Log Errors column, other sources continue |
| HTTP 429 / 403 on Tier 2 scraper | Retry 3× with backoff. On final fail, mark source Failed for this run |
| HTTP 429 from Adzuna or JSearch | Quota exceeded — skip that source for remainder of month, log warning in Run Log Errors. Auto-resumes on the 1st of next month |
| Adzuna/JSearch usage near quota | Log warning at 80% used; hard-stop at 100% |
| All Tier 1 + Tier 2 sources fail | Run Log Status = `Failed`. ntfy push at priority 5 (max + bell) |
| Sheets API down | Retry 3×. If still down, log to GitHub Actions stderr (will email Usama) |
| ntfy unavailable | Swallow silently — non-critical. Logged in Run Log |
| Workflow crashes entirely | GitHub Actions sends Usama default failure email |
| Cloudflare challenge on Glassdoor | Treat as 0 results, log warning, continue |
| RemoteOK blocks generic UA | Required UA header set; retest if blocks reappear |

**Idempotency:** Re-running the same time window twice produces the same Job IDs and same sheet state. No duplicates because of upsert-by-Job-ID.

**Quota tracking:** The Run Log Adzuna/JSearch quota columns show running total for the current calendar month. Counter resets via a tiny "month rollover" check at the top of each run.

---

## 8. Success Criteria (MVP "done")

1. Repo `Usama309/job-scraper` exists publicly with structure in §3.3
2. Four workflows exist and trigger on their schedules + manual button
3. Google Sheet exists with 6 tabs, correct headers in row 1
4. After one **manual run with `24h` window** (all 8 sources):
   - **LinkedIn** tab: ≥ 10 rows
   - **Indeed** tab: ≥ 20 rows
   - **Glassdoor** tab: 0–10 rows (acceptable to be 0)
   - **API Sources** tab: ≥ 30 rows (combined across 5 APIs)
   - **All Jobs** master tab: deduped, `Source Platforms` correctly merges multi-source matches
   - **Run Log** tab: one row with all 19 columns populated (incl. quota columns)
5. ntfy push received in ClaudePilot channel with summary
6. Re-running the same window does not create duplicate rows
7. Adzuna and JSearch crons run on schedule and their quota columns increment correctly
8. Adzuna usage stays under 250/month; JSearch under 150/month over a full month of operation

---

## 9. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LinkedIn rate-limits GitHub Actions IP | High | Medium | APIs (Tier 1) keep flowing even if LinkedIn breaks. UA rotation + jitter |
| Glassdoor Cloudflare blocks | High | Low | Tier 2 best-effort, APIs compensate |
| Adzuna 250/month exceeded | Medium | Low | 6h cron = 120/month baseline; manual runs may push over → warn at 80%, hard stop at 100% |
| JSearch 150/month exceeded | Medium | Low | 12h cron = 60/month baseline; same warn/stop logic |
| RapidAPI free plan removed for JSearch | Low | Medium | Drop JSearch from sources.json; other 7 sources unaffected |
| Adzuna signup friction (requires real-looking app description) | Medium | Low | Walk through during implementation; takes 5 min |
| Pakistan-IP issue resurfaces (GH Actions not actually US) | Low | High | Verify with first run; if confirmed, all sources affected — fallback to US VPS |
| Operator columns (V–Z) overwritten | Low | High | Hard-coded skip in upsert logic; covered by unit test |
| Sheet hits Google's 10M-cell limit after months of accumulation | Low | Medium | Phase 2 auto-prune; manual prune via filter+delete works fine for v1 |

---

## 10. Out of Scope — Phase 2

- **ClaudePilot dashboard integration** — "Run Scraper" button + "Recent Runs" widget
- **Job analyzer integration** — fills column L (Match Score) on `All Jobs` tab
- **Auto-prune** — delete master rows older than 30 days
- **Salary normalization** — parse multi-format salaries into common monthly USD
- **Resume version tracking** — auto-set column Y
- **Playwright fallback** for Glassdoor / rate-limited LinkedIn
- **Jobright source**
- **Slack / Discord webhook** in addition to ntfy
- **Geographic split** — separate US-remote and international-remote into different master tabs

---

## 11. Implementation Sequence

Ordered for fast feedback (Tier 1 APIs first = zero-risk wins):

1. Scaffold repo + 4 GitHub Actions workflows (no source code yet, just the structure)
2. Google Sheets service account setup + verify writes from a "hello world" script
3. Build `Remotive` source (Tier 1, no auth — fastest win)
4. Build `RemoteOK` source (Tier 1, no auth)
5. Build `WeWorkRemotely` source (Tier 1, no auth)
6. Build `Adzuna` source (Tier 1, signup required)
7. Build `JSearch` source (Tier 1, RapidAPI signup required)
8. Build dedup + master upsert logic — verify with all 5 API outputs
9. Build `Indeed` scraper (Tier 2 — RSS, easiest of the three)
10. Build `LinkedIn` scraper (Tier 2)
11. Build `Glassdoor` scraper (Tier 2, best-effort)
12. Run Log writing + ntfy notifications + quota tracking
13. End-to-end test against all 8 success criteria

Each step independently testable. Failure at step N does not block steps 1..N-1 from being shipped. The system has value even with only steps 1-8 done (5 working API sources).

---

## 12. Open Questions

None at design time. All earlier ambiguities resolved during brainstorming.

---

## Appendix A — Decisions Log

| Decision | Choice | Why |
|----------|--------|-----|
| Host | GitHub Actions | Free, US-based, built-in cron + manual button |
| Sheet | New dedicated sheet | Avoid polluting existing JobApplicationTracker sheet |
| Repo | New `Usama309/job-scraper` | Clean isolation |
| Manual trigger | GitHub `workflow_dispatch` (Phase 1); ClaudePilot dashboard (Phase 2) | Ship working MVP fast |
| Time window default | 6h cron | Resilient to single failed runs without heavy duplication |
| Geo filter | Any remote, any country | Per Usama's clarification 2026-05-13 |
| Sheet layout | Fields-as-columns, jobs-as-rows | Standard, sortable, filterable |
| Dedup key | `sha256(title+company)[:12]` | Deterministic, cross-source stable |
| Glassdoor reliability | Best-effort, may return 0 | Free-tier Cloudflare too aggressive |
| Source mix | Tier 1 (5 APIs) + Tier 2 (3 HTML scrapers) | Hybrid — APIs are reliable, HTML scrapers fill LinkedIn-only gaps |
| API quota management | Multi-rate cron: hourly / 6h / 12h | Adzuna and JSearch quotas too tight for hourly |
| API sources tab | One consolidated `API Sources` tab | 10 tabs would be unwieldy; column O distinguishes APIs |
| Manual trigger uses all sources | Yes | Operator may need fresh sweep; quota accepts occasional spikes |

---

**End of design spec v2.**
