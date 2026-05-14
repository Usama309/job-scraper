from __future__ import annotations

from typing import List

import gspread


def _sanitize_cell(v):
    """Prevent CSV/formula injection: prefix leading =+-@ with apostrophe."""
    if isinstance(v, str) and v and v[0] in ("=", "+", "-", "@"):
        return "'" + v
    return v


def _sanitize_row(row):
    return [_sanitize_cell(v) for v in row]


EXPECTED_TABS = [
    "All Jobs",
    "LinkedIn",
    "Indeed",
    "Glassdoor",
    "API Sources",
    "Run Log",
]

MASTER_HEADERS = [
    "Job ID", "Scraped At", "Posted Date", "Job Title", "Company Name",
    "Location", "Remote Type", "Employment Type", "Salary Range",
    "Skills / Tags", "Keyword Matched", "Match Score", "Description Snippet",
    "Source Platforms", "Primary Source", "LinkedIn URL", "Indeed URL",
    "Glassdoor URL", "Company Website", "Recruiter Name", "Recruiter Contact",
    "Application Status", "Applied On", "Follow-up Date",
    "Resume Version Used", "Notes",
]

RUN_LOG_HEADERS = [
    "Run Started", "Run Ended", "Duration (sec)", "Trigger", "Time Window",
    "LinkedIn Found", "Indeed Found", "Glassdoor Found",
    "Remotive Found", "RemoteOK Found", "WeWorkRemotely Found",
    "Adzuna Found", "JSearch Found",
    "After Dedup", "New Jobs", "Errors",
    "Adzuna Quota Used", "JSearch Quota Used", "Status",
]


class SheetsClient:
    def __init__(self, creds: dict, sheet_id: str):
        self.sheet_id = sheet_id
        self.gc = gspread.service_account_from_dict(creds)
        self.sheet = self.gc.open_by_key(sheet_id)

    def ensure_tabs(self) -> None:
        existing = {ws.title for ws in self.sheet.worksheets()}
        for tab in EXPECTED_TABS:
            if tab not in existing:
                rows = 1000
                cols = len(RUN_LOG_HEADERS) if tab == "Run Log" else len(MASTER_HEADERS)
                ws = self.sheet.add_worksheet(title=tab, rows=rows, cols=cols)
                headers: List[str] = RUN_LOG_HEADERS if tab == "Run Log" else MASTER_HEADERS
                ws.update("A1", [headers])

    def append_to_tab(self, tab: str, rows: List[List[str]]):
        if not rows:
            return
        ws = self.sheet.worksheet(tab)
        ws.append_rows([_sanitize_row(r) for r in rows], value_input_option="USER_ENTERED")

    def upsert_to_master(self, jobs: List["Job"]) -> tuple[int, int]:
        """Upsert jobs into 'All Jobs' tab. Returns (new_count, updated_count).
        Never touches columns V-Z (22-26): operator-owned.
        """
        from src.models import Job  # local import to avoid circular
        ws = self.sheet.worksheet("All Jobs")
        existing = ws.get_all_values()
        # Map: job_id -> row index (1-based, matching gspread)
        id_to_row: dict[str, int] = {}
        for i, row in enumerate(existing[1:], start=2):
            if row and row[0]:
                id_to_row[row[0]] = i

        new_rows: List[List[str]] = []
        updates = 0
        for job in jobs:
            if job.job_id in id_to_row:
                row_idx = id_to_row[job.job_id]
                # Read existing Source Platforms (column N = 14)
                current_sources = existing[row_idx - 1][13] if len(existing[row_idx - 1]) > 13 else ""
                sources_list = [s.strip() for s in current_sources.split(",") if s.strip()]
                if job.source not in sources_list:
                    sources_list.append(job.source)
                    merged = ", ".join(sources_list)
                    ws.update_cell(row_idx, 14, merged)
                # Update LinkedIn / Indeed / Glassdoor URL columns (P=16, Q=17, R=18)
                if job.source == "LinkedIn":
                    ws.update_cell(row_idx, 16, job.url)
                elif job.source == "Indeed":
                    ws.update_cell(row_idx, 17, job.url)
                elif job.source == "Glassdoor":
                    ws.update_cell(row_idx, 18, job.url)
                updates += 1
            else:
                new_rows.append(job.to_sheet_row())
                id_to_row[job.job_id] = len(existing) + len(new_rows) + 1

        if new_rows:
            ws.append_rows([_sanitize_row(r) for r in new_rows], value_input_option="USER_ENTERED")
        return len(new_rows), updates

    def write_run_log(self, stats: dict):
        ws = self.sheet.worksheet("Run Log")
        c = stats.get("counts", {})
        row = [
            stats.get("started", ""),
            stats.get("ended", ""),
            stats.get("duration_sec", 0),
            stats.get("trigger", ""),
            stats.get("time_window", ""),
            c.get("LinkedIn", 0),
            c.get("Indeed", 0),
            c.get("Glassdoor", 0),
            c.get("Remotive", 0),
            c.get("RemoteOK", 0),
            c.get("WeWorkRemotely", 0),
            c.get("Adzuna", 0),
            c.get("JSearch", 0),
            stats.get("after_dedup", 0),
            stats.get("new_jobs", 0),
            stats.get("errors", ""),
            stats.get("adzuna_quota", ""),
            stats.get("jsearch_quota", ""),
            stats.get("status", ""),
        ]
        ws.append_row(row, value_input_option="USER_ENTERED")
