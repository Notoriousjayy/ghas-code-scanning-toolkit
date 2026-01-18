from __future__ import annotations
from typing import Any

class GitHubApiError(RuntimeError):
    def __init__(
        self,
        status: int,
        message: str,
        response_json: Any = None,
        request_id: str | None = None,
    ):
        super().__init__(f"GitHub API error ({status}): {message}")
        self.status = status
        self.response_json = response_json
        self.request_id = request_id


class GitHubAuthError(GitHubApiError):
    """401"""


class GitHubNotFoundError(GitHubApiError):
    """404"""


class GitHubRateLimitError(GitHubApiError):
    def __init__(
        self,
        status: int,
        message: str,
        reset_epoch: int | None,
        response_json: Any = None,
        request_id: str | None = None,
    ):
        super().__init__(status, message, response_json=response_json, request_id=request_id)
        self.reset_epoch = reset_epoch
    """403 - Rate Limit Exceeded"""
    