from __future__ import annotations

from typing import Tuple

from .auth import get_token_from_env, get_token_from_gh_cli
from .code_scanning import CodeScanningClient
from .exceptions import GitHubApiError, GitHubAuthError, GitHubNotFoundError, GitHubRateLimitError
from .rest import GitHubRestClient

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
    token = get_token_from_env() or get_token_from_gh_cli(hostname_for_gh)
    if not token:
        raise RuntimeError(
            "No GitHub token found. Set GITHUB_TOKEN/GH_TOKEN or authenticate with `gh auth login`."
        )
    rest = GitHubRestClient(token=token, base_url=base_url, api_version=api_version)
    return rest, CodeScanningClient(rest)

__all__ = [
    "GitHubRestClient",
    "CodeScanningClient",
    "create_clients",
    "GitHubApiError",
    "GitHubAuthError",
    "GitHubNotFoundError",
    "GitHubRateLimitError",
]
