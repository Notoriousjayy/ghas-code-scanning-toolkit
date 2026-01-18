from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional

import requests

from .exceptions import GitHubApiError, GitHubAuthError, GitHubNotFoundError, GitHubRateLimitError
from .utils import (
    is_absolute_url,
    is_rate_limited,
    parse_link_header,
    req_id,
    safe_json,
    sleep_backoff,
    try_get_rate_limit_reset,
)

@dataclass
class GitHubRestClient:
    token: str
    base_url: str = "https://api.github.com"
    api_version: str = "2022-11-28"
    timeout_s: int = 30

    # Retry controls
    max_retries: int = 4
    backoff_base_s: float = 0.8
    max_backoff_s: float = 10.0

    user_agent: str = "code-scanning-api-wrapper/1.0"

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": self.api_version,
            "User-Agent": self.user_agent,
        })

    def _build_url(self, path_or_url: str) -> str:
        if is_absolute_url(path_or_url):
            return path_or_url
        return self.base_url.rstrip("/") + path_or_url

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        url = self._build_url(path)
        last_err: Optional[Exception] = None

        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json_body,
                    timeout=self.timeout_s,
                )

                if resp.status_code == 429:
                    reset = try_get_rate_limit_reset(resp)
                    raise GitHubRateLimitError(
                        resp.status_code,
                        "Rate limit hit (429).",
                        reset_epoch=reset,
                        response_json=safe_json(resp),
                        request_id=req_id(resp),
                    )

                if resp.status_code == 403 and is_rate_limited(resp):
                    reset = try_get_rate_limit_reset(resp)
                    raise GitHubRateLimitError(
                        resp.status_code,
                        "Rate limit exceeded (403).",
                        reset_epoch=reset,
                        response_json=safe_json(resp),
                        request_id=req_id(resp),
                    )

                if resp.status_code >= 400:
                    self._raise_for_status(resp)

                return resp

            except GitHubRateLimitError as e:
                # Conservative "short wait" handling
                if e.reset_epoch is not None:
                    sleep_s = max(0, e.reset_epoch - int(time.time()))
                    if sleep_s <= 15:
                        time.sleep(sleep_s + 1)
                        continue
                raise

            except (requests.Timeout, requests.ConnectionError) as e:
                last_err = e
                if attempt >= self.max_retries:
                    raise
                sleep_backoff(attempt, self.backoff_base_s, self.max_backoff_s)
                continue

            except GitHubApiError as e:
                last_err = e
                if e.status in (500, 502, 503, 504) and attempt < self.max_retries:
                    sleep_backoff(attempt, self.backoff_base_s, self.max_backoff_s)
                    continue
                raise

        if last_err:
            raise last_err
        raise RuntimeError("Unexpected request() control flow.")

    def paginate(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Iterator[Any]:
        """
        Generic pagination:
        - Supports endpoints returning JSON arrays.
        - Follows GitHub's Link: rel="next" header.
        """
        next_url: str | None = path
        params_local = dict(params or {})

        while next_url:
            resp = self.request("GET", next_url, params=params_local)
            data = resp.json()

            if not isinstance(data, list):
                raise GitHubApiError(
                    resp.status_code,
                    "Expected list response for paginated endpoint.",
                    response_json=data,
                    request_id=req_id(resp),
                )

            for item in data:
                yield item

            links = parse_link_header(resp.headers.get("Link", ""))
            next_url = links.get("next")
            # When following a full URL, params are already embedded
            params_local = {} if next_url else params_local

    def _raise_for_status(self, resp: requests.Response) -> None:
        payload = safe_json(resp)
        if isinstance(payload, dict) and "message" in payload:
            msg = str(payload.get("message", ""))
        else:
            msg = resp.text[:200]

        request_id = req_id(resp)

        if resp.status_code == 401:
            raise GitHubAuthError(resp.status_code, msg or "Unauthorized", response_json=payload, request_id=request_id)
        if resp.status_code == 404:
            raise GitHubNotFoundError(resp.status_code, msg or "Not Found", response_json=payload, request_id=request_id)

        raise GitHubApiError(resp.status_code, msg or "Request failed", response_json=payload, request_id=request_id)
