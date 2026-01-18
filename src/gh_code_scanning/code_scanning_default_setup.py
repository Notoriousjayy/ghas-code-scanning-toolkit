from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from .rest import GitHubRestClient

DefaultSetupState = Literal["configured", "disabled"]
QuerySuite = Literal["default", "extended"]
ThreatModel = Literal["remote", "remote_and_local"]
RunnerType = Literal["standard", "self_hosted"]

@dataclass
class CodeScanningDefaultSetupClient:
    gh: GitHubRestClient

    def get(self, owner: str, repo: str) -> Dict[str, Any]:
        path = f"/repos/{owner}/{repo}/code-scanning/default-setup"
        return self.gh.request("GET", path).json()

    def configure(
        self,
        owner: str,
        repo: str,
        *,
        query_suite: QuerySuite = "default",
        threat_model: ThreatModel = "remote_and_local",
        runner_type: RunnerType = "standard",
        runner_label: Optional[str] = None,
        languages: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        """
        Configure default setup for CodeQL code scanning.
        """
        path = f"/repos/{owner}/{repo}/code-scanning/default-setup"
        body: Dict[str, Any] = {
            "state": "configured",
            "query_suite": query_suite,
            "threat_model": threat_model,
            "runner_type": runner_type,
        }
        if runner_label:
            body["runner_label"] = runner_label
        if languages:
            body["languages"] = languages

        return self.gh.request("PATCH", path, json_body=body).json()

    def disable(self, owner: str, repo: str) -> Dict[str, Any]:
        path = f"/repos/{owner}/{repo}/code-scanning/default-setup"
        return self.gh.request("PATCH", path, json_body={"state": "disabled"}).json()
