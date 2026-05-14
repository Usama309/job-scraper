import os
import logging

import requests


log = logging.getLogger(__name__)


class NtfyClient:
    def __init__(self):
        self.topic = os.environ.get("NTFY_TOPIC", "")
        self.token = os.environ.get("NTFY_TOKEN", "")
        self.base = "https://ntfy.sh"

    def send(self, *, title: str, body: str, priority: int = 3):
        if not self.topic:
            log.warning("NTFY_TOPIC not set, skipping push")
            return
        url = f"{self.base}/{self.topic}"
        headers = {"Title": title, "Priority": str(priority)}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            requests.post(url, data=body.encode(), headers=headers, timeout=10)
        except Exception as e:
            log.warning(f"ntfy push failed: {e}")
