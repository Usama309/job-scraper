# Known Issues — Job Scraper

_Last updated: 2026-05-13_

---

## Active Issues

### KI-001: Glassdoor Cloudflare block (expected)

**Severity:** Low (by design)
**Status:** Accepted limitation

Glassdoor aggressively blocks scrapers via Cloudflare. The scraper handles 403 responses gracefully (returns empty list, logs warning, continues run). Zero results from Glassdoor is expected behavior in production. Covered by `test_glassdoor_handles_cloudflare_block` test.

**Mitigation:** Tier 1 APIs provide coverage when Glassdoor is blocked.
**Phase 2:** Playwright fallback is in the Phase 2 backlog.

---

### KI-002: LinkedIn guest API may be rate-limited from GitHub Actions IPs

**Severity:** Medium
**Status:** Monitor

LinkedIn's guest job-search endpoint (`/jobs-guest/jobs/api/seeMoreJobPostings/search`) does not require auth but may detect GitHub Actions runner IPs and rate-limit over time. Currently works with UA rotation and jitter.

**Detection:** If LinkedIn scraper consistently returns 0 jobs, check for 429/403 status codes in Run Log.
**Mitigation:** UA rotation + 2-5s jitter between page requests. Tier 1 APIs compensate.
**Phase 2:** Playwright fallback.

---

### KI-003: Adzuna quota tracking not implemented (Phase 2 placeholder)

**Severity:** Low
**Status:** Open

The Run Log has `Adzuna Quota Used` and `JSearch Quota Used` columns (Q, R), and `main.py` has a `# Phase 2 — read counter from sheet/file` comment. Currently these columns are written as empty strings.

**Impact:** Quota usage is not visible in the Run Log. Users must check API dashboards manually.
**Fix:** Count calls from the Run Log rows for the current calendar month and write `used/limit` format.

---

### KI-004: is_remote filter may drop valid remote jobs with unusual location strings

**Severity:** Low
**Status:** Monitor

`is_remote()` checks if location contains `remote`, `anywhere`, `wfh`, or `work from home`. Jobs described as "Distributed" or "Fully distributed" or "Global" without the word "remote" will be filtered out.

**Affected sources:** Remotive sometimes uses "Worldwide" or country-only strings without "remote".
**Current behavior:** `is_within_window` + `is_remote` + `meets_salary` must all pass. RemotiveSource hardcodes `remote_type="Remote"` but the filter checks `location`, not `remote_type`.
**Potential fix:** Also accept location "Worldwide" or check `remote_type == "Remote"` in addition to location string.

---

### KI-005: WeWorkRemotely RSS categories are hardcoded

**Severity:** Low
**Status:** Acceptable for v1

`weworkremotely.py` scrapes 5 hardcoded category RSS feeds. If WeWorkRemotely adds or renames categories, the scraper misses them. No configuration path.

**Fix (if needed):** Move category list to `config/sources.json`.

---

### KI-006: SSL warning from urllib3 on Python 3.9 (local dev only)

**Severity:** Cosmetic
**Status:** Accepted

Tests show: `NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'`

This is a macOS dev environment artifact (Python 3.9 + LibreSSL). GitHub Actions runs Python 3.11 on Ubuntu where this does not occur. Does not affect functionality or tests.

---

## Resolved Issues

_None yet._
