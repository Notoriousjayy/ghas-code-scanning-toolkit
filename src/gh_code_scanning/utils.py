from __future__ import annotations

import re
import time
from typing import Any, Dict, Optional
import requests

def is_absolute_url(s: str) -> bool:
    return s.startswith("https://") or s.startswith("http://")


def parse_link_header(link: str) -> Dict[str, str]:
    """
    Parses GitHub Link headers:
      <https://api.github.com/...page=2>; rel="next", <...>; rel="last"
    Returns mapping rel -> url.
    """
    out: Dict[str, str] = {}
    if not link:
        return out
    parts = [p.strip() for p in link.split(",")]
    for p in parts:
        m = re.match(r'<([^>]+)>\s*;\s*rel="([^"]+)"', p)
        if m:
            url, rel = m.group(1), m.group(2)
            out[rel] = url
    return out


def safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


def req_id(resp: requests.Response) -> Optional[str]:
    return resp.headers.get("X-GitHub-Request-Id")


def is_rate_limited(resp: requests.Response) -> bool:
    remaining = resp.headers.get("X-RateLimit-Remaining")
    if remaining is not None and remaining.isdigit() and int(remaining) == 0:
        return True

    payload = safe_json(resp)
    if isinstance(payload, dict):
        msg = str(payload.get("message", "")).lower()
        if "rate limit" in msg:
            return True
    return False


def try_get_rate_limit_reset(resp: requests.Response) -> Optional[int]:
    reset = resp.headers.get("X-RateLimit-Reset")
    if reset and reset.isdigit():
        return int(reset)
    return None


def sleep_backoff(attempt: int, base_s: float, max_s: float) -> None:
    sleep_s = min(max_s, base_s * (2 ** attempt))
    time.sleep(sleep_s)
