import random
import time
from typing import Optional

import requests


_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]


class HTTPClient:
    def __init__(self, max_retries: int = 3, backoff_base: float = 1.0, timeout: int = 15):
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.timeout = timeout
        self.session = requests.Session()

    def _pick_ua(self) -> str:
        return random.choice(_USER_AGENTS)

    def get(self, url: str, *, params: Optional[dict] = None, headers: Optional[dict] = None) -> requests.Response:
        merged_headers = {"User-Agent": self._pick_ua(), "Accept": "*/*"}
        if headers:
            merged_headers.update(headers)

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                r = self.session.get(url, params=params, headers=merged_headers, timeout=self.timeout)
                if r.status_code < 500 and r.status_code != 429:
                    return r
                last_exc = RuntimeError(f"HTTP {r.status_code} from {url}")
            except requests.RequestException as e:
                last_exc = e
            if attempt < self.max_retries - 1:
                time.sleep(self.backoff_base * (3 ** attempt))

        raise RuntimeError(f"Max retries exceeded for {url}: {last_exc}")

    def jitter(self, low: float = 2.0, high: float = 5.0):
        time.sleep(random.uniform(low, high))
