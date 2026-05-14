import responses
from src.sources.base import HTTPClient


@responses.activate
def test_http_client_get_returns_response():
    responses.add(responses.GET, "https://example.com/x", json={"ok": True}, status=200)
    client = HTTPClient()
    r = client.get("https://example.com/x")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@responses.activate
def test_http_client_retries_on_500():
    responses.add(responses.GET, "https://example.com/y", status=500)
    responses.add(responses.GET, "https://example.com/y", status=500)
    responses.add(responses.GET, "https://example.com/y", json={"ok": True}, status=200)
    client = HTTPClient(max_retries=3, backoff_base=0)
    r = client.get("https://example.com/y")
    assert r.status_code == 200
    assert len(responses.calls) == 3


@responses.activate
def test_http_client_gives_up_after_max_retries():
    for _ in range(4):
        responses.add(responses.GET, "https://example.com/z", status=500)
    client = HTTPClient(max_retries=3, backoff_base=0)
    import pytest
    with pytest.raises(Exception):
        client.get("https://example.com/z")


def test_http_client_rotates_user_agents():
    client = HTTPClient()
    uas = {client._pick_ua() for _ in range(50)}
    assert len(uas) >= 2  # not always same
