import os
import responses
from src.notify import NtfyClient


@responses.activate
def test_ntfy_posts_to_topic(monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "claudepilot")
    responses.add(responses.POST, "https://ntfy.sh/claudepilot", status=200)
    NtfyClient().send(title="hello", body="world")
    assert len(responses.calls) == 1
    req = responses.calls[0].request
    assert req.headers["Title"] == "hello"
    assert req.body == b"world"


@responses.activate
def test_ntfy_uses_max_priority_on_failure(monkeypatch):
    monkeypatch.setenv("NTFY_TOPIC", "claudepilot")
    responses.add(responses.POST, "https://ntfy.sh/claudepilot", status=200)
    NtfyClient().send(title="all failed", body="x", priority=5)
    assert responses.calls[0].request.headers["Priority"] == "5"


@responses.activate
def test_ntfy_swallows_errors(monkeypatch):
    """ntfy failure must not crash the run."""
    monkeypatch.setenv("NTFY_TOPIC", "claudepilot")
    responses.add(responses.POST, "https://ntfy.sh/claudepilot", status=500)
    NtfyClient().send(title="t", body="b")  # must not raise
