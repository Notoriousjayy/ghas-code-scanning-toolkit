from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Literal, Optional, Tuple, Union

import requests


# -------------------------
# Types / Enums (validated)
# -------------------------

AlertState = Literal["open", "dismissed", "fixed", "closed"]
UpdateAlertState = Literal["open", "dismissed"]
Severity = Literal["critical", "high", "medium", "low", "warning", "note", "error"]
SortField = Literal["created", "updated"]
Direction = Literal["asc", "desc"]

# GitHub docs use these exact strings for dismissed_reason
DismissedReason = Literal["false positive", "won't fix", "used in tests"]


# -------------------------
# Exceptions
# -------------------------

class GitHubApiError(RuntimeError):
    def __init__(self, status: int, message: str, response_json: Any = None, request_id: str | None = None):
        super().__init__(f"GitHub API error ({status}): {message}")
        self.status = status
        self.response_json = response_json
        self.request_id = request_id


class GitHubAuthError(GitHubApiError):
    pass


class GitHubNotFoundError(GitHubApiError):
    pass


class GitHubRateLimitError(GitHubApiError):
    def __init__(self, status: int, message: str, reset_epoch: int | None, response_json: Any = None, request_id: str | None = None):
        super().__init__(status, message, response_json=response_json, request_id=request_id)
        self.reset_epoch = reset_epoch


# -------------------------
# Auth helpers
# -------------------------

def _get_token_from_env() -> Optional[str]:
    return os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")


def _get_token_from_gh_cli(hostname: str = "github.com") -> Optional[str]:
    """
    Uses GitHub CLI to fetch an access token from the local auth context.
    Requires: gh auth login (already done per your note).
    """
    try:
        # `gh auth token` supports --hostname
        proc = subprocess.run(
            ["gh", "auth", "token", "--hostname", hostname],
            check=True,
            capture_output=True,
            text=True,
        )
        token = proc.stdout.strip()
        return token or None
    except Exception:
        return None


# -------------------------
# Low-level REST client
# -------------------------

def _parse_link_header(link: str) -> Dict[str, str]:
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


@dataclass
class GitHubRestClient:
    token: str
    base_url: str = "https://api.github.com"
    api_version: str = "2022-11-28"
    timeout_s: int = 30

    # Retry controls
    max_retries: int = 4
    backoff_base_s: float = 0.8  # exponential base
    max_backoff_s: float = 10.0

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": self.api_version,
            "User-Agent": "code-scanning-api-wrapper/1.0",
        })

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        url = self.base_url.rstrip("/") + path
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

                # Rate limit / abuse protection handling
                if resp.status_code in (429,):
                    reset = _try_get_rate_limit_reset(resp)
                    raise GitHubRateLimitError(resp.status_code, "Rate limit hit (429).", reset_epoch=reset, response_json=_safe_json(resp), request_id=_req_id(resp))

                if resp.status_code == 403 and _is_rate_limited(resp):
                    reset = _try_get_rate_limit_reset(resp)
                    raise GitHubRateLimitError(resp.status_code, "Rate limit exceeded (403).", reset_epoch=reset, response_json=_safe_json(resp), request_id=_req_id(resp))

                if resp.status_code >= 400:
                    self._raise_for_status(resp)

                return resp

            except GitHubRateLimitError as e:
                # Optionally sleep until reset if small; otherwise raise immediately
                if e.reset_epoch is not None:
                    sleep_s = max(0, e.reset_epoch - int(time.time()))
                    # Keep this conservative; you can tune based on your automation style
                    if sleep_s <= 15:
                        time.sleep(sleep_s + 1)
                        continue
                raise

            except (requests.Timeout, requests.ConnectionError) as e:
                last_err = e
                if attempt >= self.max_retries:
                    raise
                _sleep_backoff(attempt, self.backoff_base_s, self.max_backoff_s)
                continue

            except GitHubApiError as e:
                # Retry transient 5xx
                last_err = e
                if e.status in (500, 502, 503, 504) and attempt < self.max_retries:
                    _sleep_backoff(attempt, self.backoff_base_s, self.max_backoff_s)
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
        url = self.base_url.rstrip("/") + path
        params_local = dict(params or {})
        while True:
            resp = self.session.get(url, params=params_local, timeout=self.timeout_s)
            if resp.status_code >= 400:
                self._raise_for_status(resp)

            data = resp.json()
            if not isinstance(data, list):
                raise GitHubApiError(resp.status_code, "Expected list response for paginated endpoint.", response_json=data, request_id=_req_id(resp))

            for item in data:
                yield item

            links = _parse_link_header(resp.headers.get("Link", ""))
            next_url = links.get("next")
            if not next_url:
                break

            # When following a full URL, params are already embedded
            url = next_url
            params_local = {}

    def _raise_for_status(self, resp: requests.Response) -> None:
        payload = _safe_json(resp)
        msg = ""
        if isinstance(payload, dict) and "message" in payload:
            msg = str(payload.get("message", ""))
        else:
            msg = resp.text[:200]

        request_id = _req_id(resp)

        if resp.status_code in (401,):
            raise GitHubAuthError(resp.status_code, msg or "Unauthorized", response_json=payload, request_id=request_id)
        if resp.status_code in (404,):
            raise GitHubNotFoundError(resp.status_code, msg or "Not Found", response_json=payload, request_id=request_id)

        raise GitHubApiError(resp.status_code, msg or "Request failed", response_json=payload, request_id=request_id)


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return None


def _req_id(resp: requests.Response) -> Optional[str]:
    return resp.headers.get("X-GitHub-Request-Id")


def _is_rate_limited(resp: requests.Response) -> bool:
    remaining = resp.headers.get("X-RateLimit-Remaining")
    if remaining is not None and remaining.isdigit() and int(remaining) == 0:
        return True
    # Sometimes message contains "API rate limit exceeded"
    payload = _safe_json(resp)
    if isinstance(payload, dict):
        msg = str(payload.get("message", "")).lower()
        if "rate limit" in msg:
            return True
    return False


def _try_get_rate_limit_reset(resp: requests.Response) -> Optional[int]:
    reset = resp.headers.get("X-RateLimit-Reset")
    if reset and reset.isdigit():
        return int(reset)
    return None


def _sleep_backoff(attempt: int, base_s: float, max_s: float) -> None:
    sleep_s = min(max_s, base_s * (2 ** attempt))
    time.sleep(sleep_s)


# -------------------------
# Code Scanning client
# -------------------------

@dataclass
class CodeScanningClient:
    gh: GitHubRestClient

    def list_alerts_for_repo(
        self,
        owner: str,
        repo: str,
        *,
        state: AlertState = "open",
        severity: Optional[Severity] = None,
        tool_name: Optional[str] = None,
        tool_guid: Optional[str] = None,
        ref: Optional[str] = None,
        pr: Optional[int] = None,
        sort: SortField = "created",
        direction: Direction = "desc",
        assignees: Optional[str] = None,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Lists code scanning alerts for a repository with optional filtering.
        GitHub supports these query params, including tool_name/tool_guid, ref/pr, state, severity, etc. :contentReference[oaicite:3]{index=3}
        """
        if tool_name and tool_guid:
            raise ValueError("Specify only one of tool_name or tool_guid (GitHub disallows both).")

        path = f"/repos/{owner}/{repo}/code-scanning/alerts"
        params: Dict[str, Any] = {
            "state": state,
            "sort": sort,
            "direction": direction,
            "per_page": min(max(per_page, 1), 100),
        }
        if severity:
            params["severity"] = severity
        if tool_name:
            params["tool_name"] = tool_name
        if tool_guid:
            params["tool_guid"] = tool_guid
        if ref:
            params["ref"] = ref
        if pr is not None:
            params["pr"] = pr
        if assignees:
            params["assignees"] = assignees

        return list(self.gh.paginate(path, params=params))

    def get_alert(self, owner: str, repo: str, alert_number: int) -> Dict[str, Any]:
        """
        Get a single code scanning alert. :contentReference[oaicite:4]{index=4}
        """
        path = f"/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}"
        return self.gh.request("GET", path).json()

    def update_alert(
        self,
        owner: str,
        repo: str,
        alert_number: int,
        *,
        state: UpdateAlertState,
        dismissed_reason: Optional[DismissedReason] = None,
        dismissed_comment: Optional[str] = None,
        create_request: Optional[bool] = None,
        assignees: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Update alert state and/or assignees.

        GitHub requires dismissed_reason when state is dismissed, and accepts
        exact values: "false positive", "won't fix", "used in tests". :contentReference[oaicite:5]{index=5}
        """
        path = f"/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}"
        body: Dict[str, Any] = {"state": state}

        if state == "dismissed":
            if not dismissed_reason:
                raise ValueError("dismissed_reason is required when state='dismissed'")
            body["dismissed_reason"] = dismissed_reason
            if dismissed_comment is not None:
                body["dismissed_comment"] = dismissed_comment

        if create_request is not None:
            body["create_request"] = create_request

        if assignees is not None:
            body["assignees"] = assignees

        return self.gh.request("PATCH", path, json_body=body).json()

    def dismiss_alert(
        self,
        owner: str,
        repo: str,
        alert_number: int,
        *,
        reason: DismissedReason,
        comment: str,
        create_request: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Convenience wrapper for a common operation: dismiss with audit comment.
        """
        return self.update_alert(
            owner,
            repo,
            alert_number,
            state="dismissed",
            dismissed_reason=reason,
            dismissed_comment=comment,
            create_request=create_request,
        )

    def reopen_alert(self, owner: str, repo: str, alert_number: int) -> Dict[str, Any]:
        """
        Re-open a dismissed alert (sets state=open).
        """
        return self.update_alert(owner, repo, alert_number, state="open")

    def list_instances(
        self,
        owner: str,
        repo: str,
        alert_number: int,
        *,
        ref: Optional[str] = None,
        pr: Optional[int] = None,
        per_page: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Lists all instances of an alert across branches/refs. :contentReference[oaicite:6]{index=6}
        """
        path = f"/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}/instances"
        params: Dict[str, Any] = {"per_page": min(max(per_page, 1), 100)}
        if ref:
            params["ref"] = ref
        if pr is not None:
            params["pr"] = pr
        return list(self.gh.paginate(path, params=params))

    # -------------------------
    # Autofix endpoints
    # -------------------------

    def get_autofix_status(self, owner: str, repo: str, alert_number: int) -> Dict[str, Any]:
        """
        Status endpoint exists under Code Scanning REST surface. :contentReference[oaicite:7]{index=7}
        """
        path = f"/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}/autofix"
        return self.gh.request("GET", path).json()

    def create_autofix(self, owner: str, repo: str, alert_number: int) -> Dict[str, Any]:
        """
        Triggers autofix generation. Not all alerts are eligible. :contentReference[oaicite:8]{index=8}
        """
        path = f"/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}/autofix"
        return self.gh.request("POST", path).json()

    def commit_autofix(
        self,
        owner: str,
        repo: str,
        alert_number: int,
        *,
        target_ref: str,
        message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Commits an autofix to an existing branch (branch must already exist).
        GitHub's sample includes target_ref + optional message. :contentReference[oaicite:9]{index=9}
        """
        path = f"/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}/autofix/commits"
        body: Dict[str, Any] = {"target_ref": target_ref}
        if message:
            body["message"] = message
        return self.gh.request("POST", path, json_body=body).json()


# -------------------------
# Factory: "use gh CLI auth"
# -------------------------

def create_clients(
    *,
    base_url: str = "https://api.github.com",
    api_version: str = "2022-11-28",
    hostname_for_gh: str = "github.com",
) -> Tuple[GitHubRestClient, CodeScanningClient]:
    """
    Builds clients using:
      1) env token (GITHUB_TOKEN or GH_TOKEN)
      2) gh auth token
    """
    token = _get_token_from_env() or _get_token_from_gh_cli(hostname_for_gh)
    if not token:
        raise RuntimeError(
            "No GitHub token found. Set GITHUB_TOKEN/GH_TOKEN or authenticate with `gh auth login`."
        )
    rest = GitHubRestClient(token=token, base_url=base_url, api_version=api_version)
    return rest, CodeScanningClient(rest)


# -------------------------
# Example usage (manual test)
# -------------------------

if __name__ == "__main__":
    rest, cs = create_clients()
    # Replace with your target repo:
    OWNER = "OWNER"
    REPO = "REPO"

    alerts = cs.list_alerts_for_repo(OWNER, REPO, state="open", severity="high", per_page=100)
    print(f"Found {len(alerts)} open high alerts")
    if alerts:
        n = alerts[0]["number"]
        detail = cs.get_alert(OWNER, REPO, n)
        print(json.dumps(detail, indent=2))
