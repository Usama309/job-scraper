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
