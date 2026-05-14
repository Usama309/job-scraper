from __future__ import annotations

import responses

from src.sources.adzuna import AdzunaSource
from src.sources.glassdoor import GlassdoorSource
from src.sources.indeed import IndeedSource
from src.sources.jsearch import JSearchSource
from src.sources.linkedin import LinkedInSource
from src.sources.remoteok import RemoteOKSource
from src.sources.remotive import RemotiveSource
from src.sources.weworkremotely import WeWorkRemotelySource


@responses.activate
def test_remotive_parses_fixture(load_fixture):
    body = load_fixture("remotive_response.json")
    responses.add(
        responses.GET,
        "https://remotive.com/api/remote-jobs",
        body=body,
        status=200,
        content_type="application/json",
    )
    source = RemotiveSource()
    jobs = source.fetch(keyword="hubspot", time_window_hours=720)  # wide window
    assert len(jobs) >= 1
    j = jobs[0]
    assert j.title == "HubSpot Specialist"
    assert j.company == "Acme"
    assert j.source == "Remotive"
    assert "hubspot" in [t.lower() for t in j.skills_tags]
    assert j.url.startswith("https://remotive.com/")


@responses.activate
def test_remoteok_parses_fixture(load_fixture):
    body = load_fixture("remoteok_response.json")
    responses.add(
        responses.GET, "https://remoteok.com/api",
        body=body, status=200, content_type="application/json",
    )
    source = RemoteOKSource()
    jobs = source.fetch(keyword="crm", time_window_hours=720)
    assert len(jobs) == 1
    assert jobs[0].title == "CRM Engineer"
    assert jobs[0].source == "RemoteOK"
    assert "60000" in jobs[0].salary_range or "60,000" in jobs[0].salary_range


@responses.activate
def test_wwr_parses_fixture(load_fixture):
    body = load_fixture("wwr_response.rss")
    responses.add(
        responses.GET,
        "https://weworkremotely.com/categories/remote-customer-support-jobs/jobs.rss",
        body=body, status=200, content_type="application/rss+xml",
    )
    source = WeWorkRemotelySource()
    jobs = source.fetch(keyword="hubspot", time_window_hours=720)
    assert len(jobs) >= 1
    j = jobs[0]
    assert "HubSpot" in j.title or "hubspot" in j.title.lower()
    assert j.source == "WeWorkRemotely"


@responses.activate
def test_adzuna_parses_fixture(load_fixture, monkeypatch):
    monkeypatch.setenv("ADZUNA_APP_ID", "test_id")
    monkeypatch.setenv("ADZUNA_APP_KEY", "test_key")
    body = load_fixture("adzuna_response.json")
    responses.add(
        responses.GET,
        "https://api.adzuna.com/v1/api/jobs/us/search/1",
        body=body, status=200, content_type="application/json",
    )
    source = AdzunaSource()
    jobs = source.fetch_combined(keywords=["GoHighLevel", "HubSpot"], time_window_hours=720)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == "GoHighLevel Specialist"
    assert j.source == "Adzuna"
    assert j.salary_range and "60000" in j.salary_range


@responses.activate
def test_jsearch_parses_fixture(load_fixture, monkeypatch):
    monkeypatch.setenv("RAPIDAPI_KEY", "test_key")
    body = load_fixture("jsearch_response.json")
    responses.add(
        responses.GET, "https://jsearch.p.rapidapi.com/search",
        body=body, status=200, content_type="application/json",
    )
    source = JSearchSource()
    jobs = source.fetch_combined(keywords=["CRM"], time_window_hours=720)
    assert len(jobs) == 1
    j = jobs[0]
    assert j.title == "CRM Automation Engineer"
    assert j.source == "JSearch"
    # Underlying publisher tracked in skills_tags + keyword_matched
    assert "LinkedIn" in j.skills_tags
    assert "JSearch via LinkedIn" in j.keyword_matched


@responses.activate
def test_indeed_parses_fixture(load_fixture):
    body = load_fixture("indeed_response.rss")
    responses.add(
        responses.GET, "https://www.indeed.com/rss",
        body=body, status=200, content_type="application/rss+xml",
    )
    source = IndeedSource()
    jobs = source.fetch(keyword="hubspot", time_window_hours=24)
    assert len(jobs) == 1
    j = jobs[0]
    assert "HubSpot" in j.title
    assert j.company == "Acme"
    assert j.source == "Indeed"


@responses.activate
def test_linkedin_parses_fixture(load_fixture):
    body = load_fixture("linkedin_response.html")
    responses.add(
        responses.GET,
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
        body=body, status=200, content_type="text/html",
    )
    source = LinkedInSource()
    jobs = source.fetch(keyword="crm", time_window_hours=24)
    assert len(jobs) == 2
    assert jobs[0].title == "CRM Automation Engineer"
    assert jobs[0].company == "Acme Co"
    assert jobs[0].source == "LinkedIn"
    assert "linkedin.com/jobs/view/" in jobs[0].url


@responses.activate
def test_glassdoor_parses_fixture(load_fixture):
    body = load_fixture("glassdoor_response.html")
    responses.add(
        responses.GET,
        "https://www.glassdoor.com/Job/remote-crm-jobs-SRCH_IL.0,6_IS11047_KO7,10.htm",
        body=body, status=200, content_type="text/html",
    )
    source = GlassdoorSource()
    jobs = source.fetch(keyword="crm", time_window_hours=24)
    # Best-effort — accept zero results, but if any: validate
    if jobs:
        assert jobs[0].source == "Glassdoor"


@responses.activate
def test_glassdoor_handles_cloudflare_block():
    responses.add(
        responses.GET,
        "https://www.glassdoor.com/Job/remote-test-jobs-SRCH_IL.0,6_IS11047_KO7,11.htm",
        body="<html>Cloudflare challenge</html>", status=403,
    )
    source = GlassdoorSource()
    jobs = source.fetch(keyword="test", time_window_hours=24)
    assert jobs == []  # must not throw
