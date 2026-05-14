from __future__ import annotations

import responses

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
