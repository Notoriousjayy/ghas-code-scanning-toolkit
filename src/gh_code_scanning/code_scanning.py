from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .rest import GitHubRestClient
from .types import AlertState, Direction, DismissedReason, Severity, SortField, UpdateAlertState

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
        path = f"/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}/instances"
        params: Dict[str, Any] = {"per_page": min(max(per_page, 1), 100)}
        if ref:
            params["ref"] = ref
        if pr is not None:
            params["pr"] = pr
        return list(self.gh.paginate(path, params=params))

    # Autofix endpoints (status/create/commit) are explicitly called out in README :contentReference[oaicite:15]{index=15}
    def get_autofix_status(self, owner: str, repo: str, alert_number: int) -> Dict[str, Any]:
        path = f"/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}/autofix"
        return self.gh.request("GET", path).json()

    def create_autofix(self, owner: str, repo: str, alert_number: int) -> Dict[str, Any]:
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
        path = f"/repos/{owner}/{repo}/code-scanning/alerts/{alert_number}/autofix/commits"
        body: Dict[str, Any] = {"target_ref": target_ref}
        if message:
            body["message"] = message
        return self.gh.request("POST", path, json_body=body).json()
