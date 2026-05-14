import hashlib
import re


_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def normalize(s: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def compute_job_id(title: str, company: str) -> str:
    """Deterministic 12-char hash from normalized title + company."""
    key = f"{normalize(title)}|{normalize(company)}"
    return hashlib.sha256(key.encode()).hexdigest()[:12]
