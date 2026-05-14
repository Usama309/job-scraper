from __future__ import annotations

from typing import List

import gspread


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
