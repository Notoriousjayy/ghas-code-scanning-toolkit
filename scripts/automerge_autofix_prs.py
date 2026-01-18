#!/usr/bin/env python3
from __future__ import annotations

import argparse
from typing import Any, Dict, List, Optional

from gh_code_scanning import create_clients

def all_checks_success(rest, owner: str, repo: str, sha: str) -> bool:
    # Prefer check-runs API (covers GitHub Actions + other checks)
    resp = rest.request(
        "GET",
        f"/repos/{owner}/{repo}/commits/{sha}/check-runs",
        params={"per_page": 100},
    ).json()

    runs: List[Dict[str, Any]] = resp.get("check_runs", [])
    if not runs:
        # Fallback to combined status
        status = rest.request("GET", f"/repos/{owner}/{repo}/commits/{sha}/status").json()
        return status.get("state") == "success"

    for r in runs:
        if r.get("status") != "completed":
            return False
        if r.get("conclusion") != "success":
            return False
    return True

def main() -> int:
    ap = argparse.ArgumentParser(description="Auto-merge Autofix PRs when checks are green.")
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--head-prefix", default="autofix/", help="Only merge PRs whose head branch starts with this prefix.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rest, _ = create_clients()

    prs = rest.request(
        "GET",
        f"/repos/{args.owner}/{args.repo}/pulls",
        params={"state": "open", "per_page": 100},
    ).json()

    merged_any = False

    for pr in prs:
        if pr.get("draft"):
            continue

        head_ref = (pr.get("head") or {}).get("ref", "")
        if not head_ref.startswith(args.head_prefix):
            continue

        pr_number = pr["number"]
        sha = (pr.get("head") or {}).get("sha")
        if not sha:
            continue

        if not all_checks_success(rest, args.owner, args.repo, sha):
            print(f"PR #{pr_number} not mergeable yet: checks not green.")
            continue

        if args.dry_run:
            print(f"[DRY RUN] Would merge PR #{pr_number} ({head_ref})")
            merged_any = True
            continue

        merge_resp = rest.request(
            "PUT",
            f"/repos/{args.owner}/{args.repo}/pulls/{pr_number}/merge",
            json_body={"merge_method": "squash"},
        ).json()

        if merge_resp.get("merged"):
            print(f"Merged PR #{pr_number} ({head_ref})")
            merged_any = True
        else:
            print(f"Failed to merge PR #{pr_number}: {merge_resp}")

    return 0 if merged_any else 0

if __name__ == "__main__":
    raise SystemExit(main())
