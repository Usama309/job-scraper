"""CDP wrapper for Comet (Chrome) — opens pages, detects Cloudflare/403 blocks,
sends ntfy alerts when human intervention is needed, polls until resolved.

Expects Comet running with `--remote-debugging-port=9222`.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Callable, Optional
from urllib.request import urlopen, Request

import requests

log = logging.getLogger(__name__)

CDP_HOST = "http://localhost:9222"


class CometUnavailableError(RuntimeError):
    """Raised when Comet isn't running with CDP enabled."""


class BlockedError(RuntimeError):
    """Raised when a page is blocked and the user did not solve it in time."""


def _cdp_targets() -> list[dict]:
    try:
        with urlopen(f"{CDP_HOST}/json", timeout=3) as r:
            return json.loads(r.read())
    except Exception as e:
        raise CometUnavailableError(
            f"Comet CDP not reachable at {CDP_HOST}. "
            "Start Comet with --remote-debugging-port=9222"
        ) from e


def _open_page(url: str) -> str:
    """Open a new tab via CDP. Returns target id."""
    with urlopen(Request(f"{CDP_HOST}/json/new?{url}", method="PUT"), timeout=10) as r:
        return json.loads(r.read())["id"]


def _close_page(target_id: str) -> None:
    try:
        urlopen(Request(f"{CDP_HOST}/json/close/{target_id}", method="GET"), timeout=5).read()
    except Exception:
        pass


async def _eval_in_page_async(target_id: str, expression: str) -> dict:
    """Run JS in a page via CDP WebSocket. Uses aiohttp which omits the Origin
    header by default, so Comet doesn't reject the connection (Chrome 130+
    requires --remote-allow-origins for origin-bearing clients)."""
    import aiohttp  # type: ignore
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{CDP_HOST}/json", timeout=aiohttp.ClientTimeout(total=5)) as r:
            targets = await r.json()
        ws_url = next(t["webSocketDebuggerUrl"] for t in targets if t["id"] == target_id)
        async with session.ws_connect(ws_url, max_msg_size=0, timeout=15) as ws:
            await ws.send_str(json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expression, "returnByValue": True, "awaitPromise": True},
            }))
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    payload = json.loads(msg.data)
                    if payload.get("id") == 1:
                        return payload.get("result", {}).get("result", {}).get("value", {})
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                    break
    return {}


def _eval_in_page(target_id: str, expression: str) -> dict:
    """Sync wrapper around the async eval helper."""
    import asyncio
    return asyncio.run(_eval_in_page_async(target_id, expression))


def _ntfy(topic: str, title: str, body: str, priority: int = 5, click_url: Optional[str] = None) -> None:
    if not topic:
        return
    headers = {"Title": title, "Priority": str(priority), "Tags": "warning,robot"}
    if click_url:
        headers["Click"] = click_url
    try:
        requests.post(f"https://ntfy.sh/{topic}", data=body.encode(), headers=headers, timeout=10)
    except Exception as e:
        log.warning(f"ntfy push failed: {e}")


def is_blocked(html: str) -> tuple[bool, str]:
    """Detect Cloudflare / Captcha / 403 blocks. Returns (is_blocked, reason)."""
    lo = html.lower()
    if "just a moment" in lo or "cf-challenge" in lo or "challenge-platform" in lo:
        return True, "Cloudflare challenge"
    if "captcha" in lo and "verify" in lo:
        return True, "Captcha required"
    if "access denied" in lo or "you have been blocked" in lo:
        return True, "Access denied"
    if "are you a human" in lo or "are you a robot" in lo:
        return True, "Bot check"
    # Indeed-specific
    if "additional verification required" in lo or "indeed wants to make sure" in lo:
        return True, "Indeed verification"
    return False, ""


def fetch_page_html(
    url: str,
    *,
    ntfy_topic: str = "",
    label: str = "page",
    wait_for_block_solve_sec: int = 300,
    poll_interval_sec: int = 8,
) -> str:
    """Open `url` in Comet, return rendered HTML.

    If a Cloudflare/captcha block is detected, sends an ntfy push and polls
    every `poll_interval_sec` until the user solves it (or timeout).
    Raises BlockedError if not solved in time.
    """
    target_id = _open_page(url)
    try:
        time.sleep(4)  # initial render
        deadline = time.time() + wait_for_block_solve_sec
        alerted = False
        while True:
            html = _eval_in_page(target_id, "document.documentElement.outerHTML")
            blocked, reason = is_blocked(html) if isinstance(html, str) else (False, "")
            if not blocked:
                return html if isinstance(html, str) else ""
            if not alerted:
                _ntfy(
                    ntfy_topic,
                    title=f"{label}: solve {reason}",
                    body=f"Open Comet on your Mac and solve the challenge for:\n{url}\n\n"
                         f"Scraper is polling every {poll_interval_sec}s and will continue automatically.",
                    priority=5,
                    click_url=url,
                )
                alerted = True
                log.warning(f"{label} blocked ({reason}) — alerted via ntfy, polling")
            if time.time() > deadline:
                raise BlockedError(f"{label} still blocked after {wait_for_block_solve_sec}s")
            time.sleep(poll_interval_sec)
    finally:
        _close_page(target_id)


def ensure_comet_running() -> None:
    """Raise CometUnavailableError if Comet isn't reachable."""
    _cdp_targets()
