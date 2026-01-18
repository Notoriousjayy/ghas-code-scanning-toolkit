#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import logging
import time
from typing import Any, Dict, List, Optional

from gh_code_scanning import create_clients
from gh_code_scanning.exceptions import GitHubApiError, GitHubNotFoundError

log = logging.getLogger("autofix_campaign")


def utcnow_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_default_branch(rest, owner: str, repo: str) -> str:
    obj = rest.request("GET", f"/repos/{owner}/{repo}").json()
    return obj.get("default_branch") or "main"


def get_branch_sha(rest, owner: str, repo: str, branch: str) -> str:
    ref = rest.request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}").json()
    return ref["object"]["sha"]


def create_branch(rest, owner: str, repo: str, branch: str, sha: str) -> None:
    rest.request("POST", f"/repos/{owner}/{repo}/git/refs", json_body={"ref": f"refs/heads/{branch}", "sha": sha})


def create_pr(rest, owner: str, repo: str, head: str, base: str, title: str, body: str) -> Dict[str, Any]:
    return rest.request(
        "POST",
        f"/repos/{owner}/{repo}/pulls",
        json_body={"title": title, "head": head, "base": base, "body": body},
    ).json()


def wait_for_autofix_ready(cs, owner: str, repo: str, alert_number: int, timeout_s: int = 900) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            st = cs.get_autofix_status(owner, repo, alert_number)
        except GitHubNotFoundError:
            # likely not available yet
            return False
        except GitHubApiError as e:
            log.warning("Status error %s/%s #%d: %s", owner, repo, alert_number, e)
            time.sleep(10)
            continue

        # Be defensive: field names may differ; treat common possibilities
        status = (st.get("status") or st.get("state") or "").lower()
        if status in ("ready", "completed", "complete", "succeeded"):
            return True
        if status in ("failed", "error"):
            return False

        time.sleep(10)

    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--severity", default="high", choices=["critical", "high", "medium", "low", "warning", "note"])
    ap.add_argument("--max", type=int, default=3, help="Max PRs to open per run.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    rest, cs = create_clients()

    alerts = cs.list_alerts_for_repo(args.owner, args.repo, state="open", severity=args.severity, per_page=100)

    default_branch = get_default_branch(rest, args.owner, args.repo)
    base_sha = get_branch_sha(rest, args.owner, args.repo, default_branch)

    opened = 0
    for a in alerts:
        if opened >= args.max:
            break

        num = int(a["number"])
        branch = f"autofix/code-scanning-{num}"
        title = f"Autofix: Code scanning alert #{num}"
        body = f"Automated autofix campaign run at {utcnow_iso()}.\n\nAlert: {a.get('html_url','')}\n"

        if args.dry_run:
            log.info("dry-run: would create autofix + PR for #%d on %s", num, branch)
            opened += 1
            continue

        # Create branch (idempotent-ish: if exists, skip)
        try:
            create_branch(rest, args.owner, args.repo, branch, base_sha)
        except GitHubApiError as e:
            # If already exists or forbidden, skip
            log.warning("Branch create failed (may exist) %s: %s", branch, e)

        # Create autofix
        try:
            cs.create_autofix(args.owner, args.repo, num)
        except GitHubApiError as e:
            log.warning("create_autofix failed #%d: %s", num, e)
            continue

        # Wait for readiness (best-effort)
        ready = wait_for_autofix_ready(cs, args.owner, args.repo, num)
        if not ready:
            log.warning("autofix not ready or failed for #%d; skipping commit/pr", num)
            continue

        # Commit autofix to the branch
        try:
            cs.commit_autofix(args.owner, args.repo, num, target_ref=branch, message=title)
        except GitHubApiError as e:
            log.warning("commit_autofix failed #%d: %s", num, e)
            continue

        # Open PR
        try:
            pr = create_pr(rest, args.owner, args.repo, head=branch, base=default_branch, title=title, body=body)
            log.info("Opened PR: %s", pr.get("html_url"))
            opened += 1
        except GitHubApiError as e:
            log.warning("create PR failed #%d: %s", num, e)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
