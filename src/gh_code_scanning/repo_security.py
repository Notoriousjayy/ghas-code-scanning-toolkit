from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional

from .rest import GitHubRestClient

Status = Literal["enabled", "disabled"]

@dataclass
class RepoSecurityClient:
    gh: GitHubRestClient

    def set_security_and_analysis(
        self,
        owner: str,
        repo: str,
        *,
        advanced_security: Optional[Status] = None,
        code_security: Optional[Status] = None,
        secret_scanning: Optional[Status] = None,
        secret_scanning_push_protection: Optional[Status] = None,
    ) -> Dict[str, Any]:
        path = f"/repos/{owner}/{repo}"
        s_and_a: Dict[str, Any] = {}

        def add(name: str, value: Optional[Status]) -> None:
            if value is not None:
                s_and_a[name] = {"status": value}

        add("advanced_security", advanced_security)
        add("code_security", code_security)
        add("secret_scanning", secret_scanning)
        add("secret_scanning_push_protection", secret_scanning_push_protection)

        body = {"security_and_analysis": s_and_a}
        return self.gh.request("PATCH", path, json_body=body).json()
