#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import logging
import time
from typing import Any, Dict, Optional, Set, Tuple

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
    rest.request(
        "POST",
        f"/repos/{owner}/{repo}/git/refs",
        json_body={"ref": f"refs/heads/{branch}", "sha": sha},
    )


def create_pr(rest, owner: str, repo: str, head: str, base: str, title: str, body: str) -> Dict[str, Any]:
    return rest.request(
        "POST",
        f"/repos/{owner}/{repo}/pulls",
        json_body={"title": title, "head": head, "base": base, "body": body},
    ).json()


def pr_exists_for_head(rest, owner: str, repo: str, head_ref: str) -> bool:
    prs = rest.request(
        "GET",
        f"/repos/{owner}/{repo}/pulls",
        params={"state": "open", "head": head_ref, "per_page": 1},
    ).json()
    return isinstance(prs, list) and len(prs) > 0


def get_rate_limit(rest) -> Tuple[int, int]:
    # Returns (remaining, reset_epoch)
    data = rest.request("GET", "/rate_limit").json()
    core = (data.get("resources") or {}).get("core") or {}
    remaining = int(core.get("remaining") or 0)
    reset = int(core.get("reset") or int(time.time()) + 60)
    return remaining, reset


def handle_rate_limit(rest, *, sleep_on_rate_limit: bool) -> bool:
    remaining, reset = get_rate_limit(rest)
    if remaining > 0:
        return False
    if not sleep_on_rate_limit:
        return True
    now = time.time()
    delay = max(0.0, (reset - now) + 5.0)
    log.warning("Rate limit exhausted; sleeping %.0fs until reset.", delay)
    time.sleep(delay)
    return False


def is_rate_limit_error(e: Exception) -> bool:
    return "rate limit exceeded" in str(e).lower()


def is_transient_server_error(e: Exception) -> bool:
    code = getattr(e, "status_code", None)
    if code in (500, 502, 503, 504):
        return True
    # Some wrappers do not expose status_code reliably; keep message-based fallback
    msg = str(e).lower()
    return "github api error (500)" in msg or "github api error (502)" in msg or "github api error (503)" in msg


def is_unsupported_autofix(e: Exception) -> bool:
    # GitHub returns 422 with message "Alert is not supported by autofix."
    return "not supported by autofix" in str(e).lower()


def alert_rule_id(alert: Dict[str, Any]) -> Optional[str]:
    rule = alert.get("rule") or {}
    rid = rule.get("id") or rule.get("rule_id") or rule.get("name")
    if rid is None:
        return None
    return str(rid)


def retry_call(fn, *, rest=None, sleep_on_rate_limit: bool = True, retries: int = 3, base_delay: float = 2.0):
    for attempt in range(retries + 1):
        try:
            return fn()
        except GitHubApiError as e:
            if is_rate_limit_error(e) and rest is not None:
                stop = handle_rate_limit(rest, sleep_on_rate_limit=sleep_on_rate_limit)
                if stop:
                    raise
                continue

            if is_transient_server_error(e) and attempt < retries:
                delay = base_delay * (2**attempt)
                log.warning("Transient error; retrying in %.1fs: %s", delay, e)
                time.sleep(delay)
                continue

            raise


def wait_for_autofix_ready(cs, owner: str, repo: str, alert_number: int, timeout_s: int = 900) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            st = cs.get_autofix_status(owner, repo, alert_number)
        except GitHubNotFoundError:
            return False
        except GitHubApiError as e:
            log.warning("Status error %s/%s #%d: %s", owner, repo, alert_number, e)
            time.sleep(10)
            continue

        status = (st.get("status") or st.get("state") or "").lower()
        if status in ("ready", "completed", "complete", "succeeded", "success"):
            return True
        if status in ("failed", "error"):
            return False

        time.sleep(10)

    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Create Autofix PRs for code scanning alerts (if applicable).")
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument(
        "--severity",
        default="all",
        choices=["all", "critical", "high", "medium", "low", "warning", "note"],
        help="Filter by severity. Use 'all' to process all open alerts.",
    )
    ap.add_argument(
        "--max",
        type=int,
        default=10,
        help="Max alerts to process per run (caps API usage even if autofix is unsupported).",
    )
    ap.add_argument(
        "--max-prs",
        type=int,
        default=10,
        help="Max PRs to open per run (additional safety cap).",
    )
    ap.add_argument("--timeout-s", type=int, default=900, help="Seconds to wait for autofix readiness per alert.")
    ap.add_argument("--no-sleep-on-rate-limit", action="store_true", help="Fail fast instead of sleeping on 403 limits.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    rest, cs = create_clients()

    severity: Optional[str] = None if args.severity == "all" else args.severity
    alerts = cs.list_alerts_for_repo(args.owner, args.repo, state="open", severity=severity, per_page=100)

    default_branch = get_default_branch(rest, args.owner, args.repo)
    base_sha = get_branch_sha(rest, args.owner, args.repo, default_branch)

    processed = 0
    opened_prs = 0
    unsupported_rules: Set[str] = set()

    for a in alerts:
        if processed >= args.max:
            break
        if opened_prs >= args.max_prs:
            break

        processed += 1

        num = int(a["number"])
        branch = f"autofix/code-scanning-{num}"
        head_ref = f"{args.owner}:{branch}"

        rid = alert_rule_id(a)
        if rid and rid in unsupported_rules:
            log.info("Skipping #%d: rule %s previously marked unsupported for autofix in this run", num, rid)
            continue

        # Idempotency: if an open PR already exists for this head, skip early
        try:
            if pr_exists_for_head(rest, args.owner, args.repo, head_ref=head_ref):
                log.info("Skipping #%d: open PR already exists for %s", num, head_ref)
                continue
        except GitHubApiError as e:
            log.warning("PR existence check failed for #%d (%s): %s", num, head_ref, e)

        title = f"Autofix: Code scanning alert #{num}"
        body = f"Automated autofix campaign run at {utcnow_iso()}.\n\nAlert: {a.get('html_url','')}\n"

        if args.dry_run:
            log.info("dry-run: would create autofix + PR for #%d on %s", num, branch)
            opened_prs += 1
            continue

        # Create autofix (best-effort)
        try:
            retry_call(
                lambda: cs.create_autofix(args.owner, args.repo, num),
                rest=rest,
                sleep_on_rate_limit=(not args.no_sleep_on_rate_limit),
                retries=2,
            )
        except GitHubApiError as e:
            if is_unsupported_autofix(e):
                if rid:
                    unsupported_rules.add(rid)
                log.warning("create_autofix failed #%d: %s", num, e)
                continue
            log.warning("create_autofix failed #%d: %s", num, e)
            if is_rate_limit_error(e) and args.no_sleep_on_rate_limit:
                return 1
            continue

        ready = wait_for_autofix_ready(cs, args.owner, args.repo, num, timeout_s=args.timeout_s)
        if not ready:
            log.warning("autofix not ready or failed for #%d; skipping commit/pr", num)
            continue

        # Create branch (best-effort; may already exist)
        try:
            retry_call(
                lambda: create_branch(rest, args.owner, args.repo, branch, base_sha),
                rest=rest,
                sleep_on_rate_limit=(not args.no_sleep_on_rate_limit),
                retries=1,
            )
        except GitHubApiError as e:
            log.warning("Branch create failed (may exist) %s: %s", branch, e)

        # Commit autofix to the branch (retry on transient 5xx)
        try:
            retry_call(
                lambda: cs.commit_autofix(args.owner, args.repo, num, target_ref=branch, message=title),
                rest=rest,
                sleep_on_rate_limit=(not args.no_sleep_on_rate_limit),
                retries=3,
            )
        except GitHubApiError as e:
            log.warning("commit_autofix failed #%d: %s", num, e)
            if is_rate_limit_error(e) and args.no_sleep_on_rate_limit:
                return 1
            continue

        # Open PR
        try:
            pr = retry_call(
                lambda: create_pr(rest, args.owner, args.repo, head=branch, base=default_branch, title=title, body=body),
                rest=rest,
                sleep_on_rate_limit=(not args.no_sleep_on_rate_limit),
                retries=2,
            )
            log.info("Opened PR: %s", pr.get("html_url"))
            opened_prs += 1
        except GitHubApiError as e:
            log.warning("create PR failed #%d: %s", num, e)
            if is_rate_limit_error(e) and args.no_sleep_on_rate_limit:
                return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
