#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import time
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from gh_code_scanning import create_clients
from gh_code_scanning.exceptions import GitHubApiError, GitHubNotFoundError, GitHubRateLimitError

log = logging.getLogger("enable_automerge_all_repos")


def _sleep_with_log(seconds: int) -> None:
    if seconds <= 0:
        return
    log.warning("Sleeping %ds", seconds)
    time.sleep(seconds)


def _is_org(rest, owner: str) -> bool:
    obj = rest.request("GET", f"/users/{owner}").json()
    return (obj.get("type") or "").lower() == "organization"


def list_repos(
    rest,
    owner: str,
    include_forks: bool,
    include_archived: bool,
    visibility: str = "all",
) -> List[Dict[str, Any]]:
    """
    Returns repo objects including name, archived, fork, default_branch, private, etc.
    """
    if _is_org(rest, owner):
        path = f"/orgs/{owner}/repos"
    else:
        path = f"/users/{owner}/repos"

    params = {"per_page": 100, "type": "owner", "sort": "full_name", "direction": "asc"}
    if visibility and visibility != "all":
        # REST supports "type" more than "visibility" on these endpoints, but keep this hook.
        params["visibility"] = visibility

    repos: List[Dict[str, Any]] = []
    for r in rest.paginate(path, params=params):
        if not include_forks and r.get("fork"):
            continue
        if not include_archived and r.get("archived"):
            continue
        repos.append(r)
    return repos


def update_repo_settings(
    rest,
    owner: str,
    repo: str,
    *,
    allow_auto_merge: bool,
    delete_branch_on_merge: bool,
    merge_method: str,
    dry_run: bool,
) -> None:
    """
    PATCH /repos/{owner}/{repo}
    """
    payload: Dict[str, Any] = {
        "allow_auto_merge": allow_auto_merge,
        "delete_branch_on_merge": delete_branch_on_merge,
    }

    # Ensure at least one merge method is enabled. We “prefer” one but do not disable others unless you want to.
    # (Disabling merge methods can be disruptive.)
    if merge_method == "squash":
        payload["allow_squash_merge"] = True
    elif merge_method == "merge":
        payload["allow_merge_commit"] = True
    elif merge_method == "rebase":
        payload["allow_rebase_merge"] = True

    if dry_run:
        log.info("dry-run: would PATCH repo settings %s/%s payload=%s", owner, repo, payload)
        return

    rest.request("PATCH", f"/repos/{owner}/{repo}", json_body=payload)
    log.info("Repo settings updated: %s/%s (allow_auto_merge=%s)", owner, repo, allow_auto_merge)


def get_default_branch(rest, owner: str, repo: str) -> str:
    obj = rest.request("GET", f"/repos/{owner}/{repo}").json()
    return obj.get("default_branch") or "main"


def get_branch_protection(rest, owner: str, repo: str, branch: str) -> Optional[Dict[str, Any]]:
    try:
        return rest.request("GET", f"/repos/{owner}/{repo}/branches/{branch}/protection").json()
    except GitHubNotFoundError:
        return None


def discover_required_checks(rest, owner: str, repo: str, branch: str) -> List[str]:
    """
    Discover check-run names on the latest commit of the default branch.
    Uses:
      GET /repos/{owner}/{repo}/commits/{branch}
      GET /repos/{owner}/{repo}/commits/{sha}/check-runs
    """
    try:
        commit = rest.request("GET", f"/repos/{owner}/{repo}/commits/{branch}").json()
        sha = commit["sha"]
    except GitHubApiError as e:
        log.warning("Cannot get latest commit for %s/%s@%s: %s", owner, repo, branch, e)
        return []

    try:
        checks = rest.request(
            "GET",
            f"/repos/{owner}/{repo}/commits/{sha}/check-runs",
            params={"per_page": 100},
        ).json()
    except GitHubApiError as e:
        log.warning("Cannot list check-runs for %s/%s@%s: %s", owner, repo, sha[:7], e)
        return []

    names: List[str] = []
    for cr in (checks.get("check_runs") or []):
        name = cr.get("name")
        status = (cr.get("status") or "").lower()
        if not name or status not in ("completed", "in_progress", "queued"):
            continue
        names.append(name)

    # Deduplicate while preserving order
    seen: Set[str] = set()
    out: List[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)

    return out


def put_branch_protection(
    rest,
    owner: str,
    repo: str,
    branch: str,
    *,
    required_checks: List[str],
    strict_checks: bool,
    required_approvals_if_no_checks: int,
    enforce_admins: bool,
    dry_run: bool,
) -> None:
    """
    PUT /repos/{owner}/{repo}/branches/{branch}/protection

    Strategy:
      - If we have checks: require them; do NOT require reviews by default.
      - If we have no checks: require approving reviews (fallback) so auto-merge is meaningful.
    """
    required_status_checks: Optional[Dict[str, Any]] = None
    required_reviews: Optional[Dict[str, Any]] = None

    if required_checks:
        required_status_checks = {"strict": strict_checks, "contexts": required_checks}
        required_reviews = None
    else:
        if required_approvals_if_no_checks > 0:
            required_reviews = {
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": False,
                "required_approving_review_count": required_approvals_if_no_checks,
            }
        required_status_checks = None

    payload: Dict[str, Any] = {
        "required_status_checks": required_status_checks,
        "enforce_admins": enforce_admins,
        "required_pull_request_reviews": required_reviews,
        "restrictions": None,
    }

    if dry_run:
        log.info("dry-run: would PUT branch protection %s/%s@%s payload=%s", owner, repo, branch, payload)
        return

    rest.request("PUT", f"/repos/{owner}/{repo}/branches/{branch}/protection", json_body=payload)
    log.info(
        "Branch protection set: %s/%s@%s (checks=%d, approvals_fallback=%d)",
        owner,
        repo,
        branch,
        len(required_checks),
        required_approvals_if_no_checks if not required_checks else 0,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Enable repo auto-merge and ensure default-branch requirements for auto-merge.")
    ap.add_argument("--owner", required=True, help="User or org name (e.g., Notoriousjayy)")
    ap.add_argument("--include-forks", action="store_true", help="Include forked repos")
    ap.add_argument("--include-archived", action="store_true", help="Include archived repos")
    ap.add_argument("--visibility", default="all", choices=["all", "public", "private"], help="Repo visibility filter")
    ap.add_argument("--merge-method", default="squash", choices=["squash", "merge", "rebase"], help="Preferred merge method")
    ap.add_argument("--no-delete-branch-on-merge", action="store_true", help="Do not enable delete_branch_on_merge")
    ap.add_argument("--strict-checks", action="store_true", default=True, help="Use strict status checks (require up-to-date)")
    ap.add_argument("--enforce-admins", action="store_true", default=False, help="Apply branch protection to admins too")
    ap.add_argument("--only-if-unprotected", action="store_true", default=True, help="Only set protection if none exists")
    ap.add_argument("--force", action="store_true", help="Override existing branch protection")
    ap.add_argument("--required-approvals-if-no-checks", type=int, default=1, help="Fallback approvals if no checks discovered")
    ap.add_argument("--sleep-s", type=float, default=0.25, help="Small sleep between repos to be gentle")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--max-repos", type=int, default=0, help="If >0, limit how many repos are processed")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    rest, _cs = create_clients()

    repos = list_repos(
        rest,
        args.owner,
        include_forks=args.include_forks,
        include_archived=args.include_archived,
        visibility=args.visibility,
    )

    if args.max_repos and args.max_repos > 0:
        repos = repos[: args.max_repos]

    log.info("Processing %d repos under %s", len(repos), args.owner)

    for r in repos:
        name = r.get("name")
        if not name:
            continue

        try:
            # 1) Enable repo-level auto-merge setting
            update_repo_settings(
                rest,
                args.owner,
                name,
                allow_auto_merge=True,
                delete_branch_on_merge=not args.no_delete_branch_on_merge,
                merge_method=args.merge_method,
                dry_run=args.dry_run,
            )

            # 2) Ensure branch requirements exist on default branch (branch protection)
            branch = r.get("default_branch") or get_default_branch(rest, args.owner, name)
            existing = get_branch_protection(rest, args.owner, name, branch)

            if existing and args.only_if_unprotected and not args.force:
                log.info("Skipping protection for %s/%s@%s (already protected)", args.owner, name, branch)
                continue

            checks = discover_required_checks(rest, args.owner, name, branch)
            put_branch_protection(
                rest,
                args.owner,
                name,
                branch,
                required_checks=checks,
                strict_checks=args.strict_checks,
                required_approvals_if_no_checks=args.required_approvals_if_no_checks,
                enforce_admins=args.enforce_admins,
                dry_run=args.dry_run,
            )

        except GitHubRateLimitError as e:
            # If your rest client exposes reset times you can compute exact waits; keep simple here.
            log.warning("Rate limit encountered while processing %s: %s", name, e)
            _sleep_with_log(60)
        except GitHubApiError as e:
            log.warning("Failed repo %s/%s: %s", args.owner, name, e)

        time.sleep(args.sleep_s)

    log.info("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
