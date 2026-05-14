from src.filters import normalize, compute_job_id


def test_normalize_lowercases():
    assert normalize("Hello World") == "hello world"


def test_normalize_strips_punctuation():
    assert normalize("Sr. Engineer, CRM!") == "sr engineer crm"


def test_normalize_collapses_whitespace():
    assert normalize("foo   bar\t\nbaz") == "foo bar baz"


def test_compute_job_id_deterministic():
    a = compute_job_id("CRM Engineer", "Acme Co")
    b = compute_job_id("CRM Engineer", "Acme Co")
    assert a == b
    assert len(a) == 12


def test_compute_job_id_normalizes():
    a = compute_job_id("CRM Engineer", "Acme Co")
    b = compute_job_id("crm engineer", "acme co")
    c = compute_job_id("  CRM   Engineer ", "Acme,  Co")
    assert a == b == c


def test_compute_job_id_distinct_per_company():
    assert compute_job_id("CRM Engineer", "Acme") != compute_job_id("CRM Engineer", "Beta")


from datetime import datetime, timedelta, timezone
from src.filters import is_within_window, is_remote, meets_salary


def _job_with(posted_date=None, location="Remote", salary=None):
    from src.models import Job
    return Job(
        job_id="x", scraped_at=datetime.now(timezone.utc),
        posted_date=posted_date, title="t", company="c", location=location,
        remote_type=None, employment_type=None, salary_range=salary,
        skills_tags=[], keyword_matched="kw", description_snippet="",
        source="Remotive", url="https://x",
    )


def test_is_within_window_recent_iso_passes():
    recent = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    assert is_within_window(_job_with(posted_date=recent), hours=6)


def test_is_within_window_old_fails():
    old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    assert not is_within_window(_job_with(posted_date=old), hours=6)


def test_is_within_window_no_date_passes():
    """If posted_date missing, keep the job (don't drop ambiguous data)."""
    assert is_within_window(_job_with(posted_date=None), hours=6)


def test_is_remote_accepts_keywords():
    assert is_remote(_job_with(location="Fully Remote"))
    assert is_remote(_job_with(location="Anywhere"))
    assert is_remote(_job_with(location="Work from home — US"))
    assert is_remote(_job_with(location="WFH"))


def test_is_remote_rejects_onsite():
    assert not is_remote(_job_with(location="New York, NY"))
    assert not is_remote(_job_with(location="On-site, Berlin"))


def test_meets_salary_keeps_unlisted():
    assert meets_salary(_job_with(salary=None), min_monthly_usd=2500)
    assert meets_salary(_job_with(salary=""), min_monthly_usd=2500)


def test_meets_salary_drops_low_listed():
    assert not meets_salary(_job_with(salary="$1,500/month"), min_monthly_usd=2500)


def test_meets_salary_keeps_high_listed():
    assert meets_salary(_job_with(salary="$90,000/year"), min_monthly_usd=2500)
    assert meets_salary(_job_with(salary="$45/hour"), min_monthly_usd=2500)


def test_is_remote_accepts_remote_type_flag():
    """C1 regression: remote_type='Remote' overrides confusing location strings."""
    # Remotive returns locations like "USA Only", "Worldwide" — they ARE remote
    assert is_remote(_job_with(location="USA Only")) is False or \
        is_remote(type(_job_with()).__call__(
            **{**_job_with().__dict__, "location": "USA Only", "remote_type": "Remote"}
        ))


def test_is_remote_trusts_source_remote_type():
    from src.models import Job
    from datetime import datetime, timezone
    j = Job(
        job_id="x", scraped_at=datetime.now(timezone.utc),
        posted_date=None, title="t", company="c",
        location="USA Only",  # no "remote" keyword
        remote_type="Remote",  # but source confirmed remote
        employment_type=None, salary_range=None,
        skills_tags=[], keyword_matched="kw", description_snippet="",
        source="Remotive", url="https://x",
    )
    assert is_remote(j)


def test_is_remote_rejects_onsite_even_with_remote_type():
    from src.models import Job
    from datetime import datetime, timezone
    j = Job(
        job_id="x", scraped_at=datetime.now(timezone.utc),
        posted_date=None, title="t", company="c",
        location="Hybrid - NYC",
        remote_type="Remote",
        employment_type=None, salary_range=None,
        skills_tags=[], keyword_matched="kw", description_snippet="",
        source="X", url="https://x",
    )
    assert not is_remote(j)


def test_meets_salary_k_suffix_annual():
    """I6 regression: $60k-$90k must be detected as $60k/year ≈ $5000/mo, not as $9600/mo hourly."""
    j = _job_with(salary="$60k-$90k")
    assert meets_salary(j, min_monthly_usd=2500)


def test_meets_salary_k_suffix_low_dropped():
    """A 20k/year role should be filtered (under $2500/mo)."""
    j = _job_with(salary="$20k/year")
    assert not meets_salary(j, min_monthly_usd=2500)


def test_meets_salary_k_per_month():
    """$5k/month should be kept."""
    j = _job_with(salary="$5k/month")
    assert meets_salary(j, min_monthly_usd=2500)
