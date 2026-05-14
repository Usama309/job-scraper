from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Job:
    job_id: str
    scraped_at: datetime
    posted_date: Optional[str]
    title: str
    company: str
    location: str
    remote_type: Optional[str]
    employment_type: Optional[str]
    salary_range: Optional[str]
    skills_tags: list[str]
    keyword_matched: str
    description_snippet: str
    source: str
    url: str
    company_website: Optional[str] = None
    recruiter_name: Optional[str] = None
    recruiter_contact: Optional[str] = None

    def to_sheet_row(self) -> list[str]:
        """Serialize to 26-column row matching sheet columns A-Z."""
        scraped = self.scraped_at.strftime("%Y-%m-%d %H:%M UTC")
        url_li = self.url if self.source == "LinkedIn" else ""
        url_in = self.url if self.source == "Indeed" else ""
        url_gd = self.url if self.source == "Glassdoor" else ""
        return [
            self.job_id,                              # A
            scraped,                                  # B
            self.posted_date or "",                   # C
            self.title,                               # D
            self.company,                             # E
            self.location,                            # F
            self.remote_type or "",                   # G
            self.employment_type or "",               # H
            self.salary_range or "",                  # I
            ", ".join(self.skills_tags),              # J
            self.keyword_matched,                     # K
            "",                                       # L: Match Score (analyzer fills)
            self.description_snippet,                 # M
            self.source,                              # N: Source Platforms
            self.source,                              # O: Primary Source
            url_li,                                   # P
            url_in,                                   # Q
            url_gd,                                   # R
            self.company_website or "",               # S
            self.recruiter_name or "",                # T
            self.recruiter_contact or "",             # U
            "",                                       # V: Application Status (operator)
            "",                                       # W: Applied On (operator)
            "",                                       # X: Follow-up Date (operator)
            "",                                       # Y: Resume Version (operator)
            "",                                       # Z: Notes (operator)
        ]
