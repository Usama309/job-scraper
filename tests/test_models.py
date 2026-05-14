from datetime import datetime
from src.models import Job


def test_job_required_fields():
    job = Job(
        job_id="abc123def456",
        scraped_at=datetime(2026, 5, 13, 14, 0),
        posted_date="2026-05-13",
        title="CRM Engineer",
        company="Acme",
        location="Remote (US)",
        remote_type="Remote",
        employment_type="Full-time",
        salary_range="$90k-$110k",
        skills_tags=["HubSpot", "Zapier"],
        keyword_matched="HubSpot",
        description_snippet="We are looking for...",
        source="LinkedIn",
        url="https://linkedin.com/jobs/123",
    )
    assert job.title == "CRM Engineer"
    assert job.skills_tags == ["HubSpot", "Zapier"]
    assert job.company_website is None
    assert job.recruiter_name is None


def test_job_to_sheet_row_order():
    """The dataclass must serialize to a 26-column list matching sheet schema A-Z."""
    job = Job(
        job_id="abc", scraped_at=datetime(2026, 5, 13, 14, 0),
        posted_date="2026-05-13", title="T", company="C", location="L",
        remote_type="Remote", employment_type="Full-time",
        salary_range=None, skills_tags=[], keyword_matched="kw",
        description_snippet="snip", source="Remotive", url="https://x",
    )
    row = job.to_sheet_row()
    assert len(row) == 26
    assert row[0] == "abc"                            # A: Job ID
    assert row[1] == "2026-05-13 14:00 UTC"           # B: Scraped At
    assert row[3] == "T"                              # D: Title
    assert row[4] == "C"                              # E: Company
    assert row[13] == "Remotive"                      # N: Source Platforms
    assert row[14] == "Remotive"                      # O: Primary Source
    assert row[21] == ""                              # V: Application Status (operator)
    assert row[25] == ""                              # Z: Notes (operator)
