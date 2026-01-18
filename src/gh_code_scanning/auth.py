from __future__ import annotations

import os
import subprocess
from typing import Optional

def get_token_from_env() -> Optional[str]:
    return os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")


def get_token_from_gh_cli(hostname: str = "github.com") -> Optional[str]:
    """
    Uses GitHub CLI to fetch an access token from the local auth context.
    Requires: gh auth login
    """
    try:
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
