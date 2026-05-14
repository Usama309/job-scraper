# Architecture Decision Records — Job Scraper

---

## ADR-001: Host on GitHub Actions instead of VPS

**Date:** 2026-05-13
**Status:** Accepted

**Context:** Usama's operator in Pakistan applies for jobs. Pakistani IPs get geolocation-filtered to Pakistan-region results on LinkedIn/Indeed/Glassdoor, missing US-remote roles.

**Decision:** Use GitHub Actions (`ubuntu-latest`) as the execution platform.

**Reasons:**
- GitHub Actions runners are US-based by default — solves geolocation at zero cost
- 2,000 free minutes/month is sufficient for hourly + 6h + 12h schedules combined
- Built-in cron scheduling + `workflow_dispatch` (manual button)
- Secrets management, logs, and retry all built in
- Decoupled from Hostinger VPS (which may not be US-based)

---

## ADR-002: Multi-rate cron (hourly / 6h / 12h) to respect API quotas

**Date:** 2026-05-13
**Status:** Accepted

**Context:** Adzuna allows 250 calls/month free; JSearch allows 150 calls/month free. Running hourly would blow both quotas in 2-4 days.

**Decision:** Three separate workflow files:
- Hourly: Remotive, RemoteOK, WeWorkRemotely, LinkedIn, Indeed, Glassdoor (no per-call quotas)
- Every 6h: Adzuna only → 4 runs/day × 30 = 120 calls/month (under 250 limit)
- Every 12h: JSearch only → 2 runs/day × 30 = 60 calls/month (under 150 limit)

**Consequence:** Adzuna and JSearch results are slightly less fresh than Tier 1 no-quota sources. Acceptable.

---

## ADR-003: One consolidated `API Sources` tab instead of one tab per API

**Date:** 2026-05-13
**Status:** Accepted

**Context:** 5 API sources would create 10 tabs total if each had its own tab.

**Decision:** All 5 API sources write to a single `API Sources` tab. Column O (`Primary Source`) identifies the originating API. Users can filter by column O to isolate results from a specific API.

---

## ADR-004: Dedup key = sha256(normalize(title) + "|" + normalize(company))[:12]

**Date:** 2026-05-13
**Status:** Accepted

**Context:** The same job can appear on LinkedIn, Indeed, Glassdoor, and JSearch simultaneously. We need stable cross-source deduplication without a canonical job ID.

**Decision:** Hash normalized title + company name. Normalization: lowercase, strip punctuation, collapse whitespace.

**Tradeoff:** Two different jobs at the same company with identical normalized titles will collide. This is extremely rare for real job postings and acceptable in v1.

---

## ADR-005: Operator columns V-Z are never overwritten by scraper

**Date:** 2026-05-13
**Status:** Accepted

**Context:** The operator (or Usama) manually tracks Application Status (V), Applied On (W), Follow-up Date (X), Resume Version (Y), Notes (Z) on the All Jobs master tab. Re-scraping the same time window must not erase this work.

**Decision:** `upsert_to_master()` in `sheets.py` only updates columns A-U for existing job rows. Columns 22-26 (V-Z) are never touched. Enforced by a dedicated unit test.

---

## ADR-006: Tier 2 scrapers are best-effort, never block Tier 1

**Date:** 2026-05-13
**Status:** Accepted

**Context:** LinkedIn, Indeed, and Glassdoor HTML scrapers can be blocked by Cloudflare, rate limits, or structural HTML changes. Adzuna and JSearch APIs are reliable.

**Decision:** Each source is wrapped in `try/except`. A source failure logs to Run Log errors and sends a partial-failure ntfy, but never crashes the run. The `status` field is `OK` | `Partial` | `Failed`.

---

## ADR-007: Adzuna uses one fetch_combined call per run (OR query)

**Date:** 2026-05-13
**Status:** Accepted

**Context:** Adzuna quota is 250/month. If we made one call per keyword (~40 keywords), that would be 40 calls/run × 4 runs/day = 4,800 calls/day — instant quota burn.

**Decision:** Single call per run using `what_or` parameter with all keywords concatenated. Returns up to 50 results per call. JSearch uses the same strategy with its `query` parameter.

---

## ADR-008: Salary filter — keep jobs with no salary listed

**Date:** 2026-05-13
**Status:** Accepted

**Context:** Many remote jobs (especially in CRM/automation) don't list salary. A hard filter would drop most results.

**Decision:** `meets_salary` returns `True` if `salary_range` is None or unparseable. Only drops jobs where salary is explicitly listed AND below $2,500/month. Floor is configurable in `config/filters.json`.

---

## ADR-009: New dedicated Google Sheet, not existing JobApplicationTracker

**Date:** 2026-05-13
**Status:** Accepted

**Context:** Usama has an existing job tracker sheet. The scraper outputs dozens of raw rows that haven't been filtered/applied.

**Decision:** New sheet `Job Scraper` specifically for scraper output. The existing tracker is operator-maintained. Keeps concerns separated.

---

## ADR-010: Python dataclass for Job model (not Pydantic)

**Date:** 2026-05-13
**Status:** Accepted

**Context:** The data model is simple, flat, and used only internally. Pydantic would add validation overhead and a dependency.

**Decision:** Standard `@dataclass` from stdlib. Validation happens at the source level (skip rows without title/company). This keeps the `requirements.txt` minimal.
