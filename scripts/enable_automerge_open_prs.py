#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import time
from typing import Any, Dict, Iterable, Optional, Tuple

from gh_code_scanning import create_clients
from gh_code_scanning.exceptions import GitHubApiError, GitHubRateLimitError, GitHubNotFoundError

log = logging.getLogger("enable_automerge_open_prs")

ENABLE_AUTOMERGE_MUTATION = """
mutation($pullRequestId: ID!, $mergeMethod: PullRequestMergeMethod!) {
  enablePullRequestAutoMerge(input: { pullRequestId: $pullRequestId, mergeMethod: $mergeMethod }) {
    pullRequest { number }
  }
}
"""

# Query minimal repo metadata
def iter_repos(rest, owner: str, max_repos: Optional[int] = None) -> Iterable[Dict[str, Any]]:
    who = rest.request("GET", f"/users/{owner}").json()
    is_org = (who.get("type") == "Organization")

    if is_org:
        path = f"/orgs/{owner}/repos"
        params = {"per_page": 100, "type": "all"}
    else:
        path = f"/users/{owner}/repos"
        params = {"per_page": 100, "type": "owner"}

    count = 0
    for repo in rest.paginate(path, params=params):
        yield repo
        count += 1
        if max_repos is not None and count >= max_repos:
            return


def iter_open_prs(rest, owner: str, repo: str, max_prs: Optional[int] = None) -> Iterable[Dict[str, Any]]:
    count = 0
    for pr in rest.paginate(
        f"/repos/{owner}/{repo}/pulls",
        params={"state": "open", "per_page": 100},
    ):
        yield pr
        count += 1
        if max_prs is not None and count >= max_prs:
            return


def graphql(rest, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
    resp = rest.request("POST", "/graphql", json_body={"query": query, "variables": variables})
    payload = resp.json()
    if isinstance(payload, dict) and payload.get("errors"):
        raise GitHubApiError(400, "GraphQL error", response_json=payload, request_id=None)
    if not isinstance(payload, dict):
        raise GitHubApiError(400, "Unexpected GraphQL payload", response_json={"payload": payload}, request_id=None)
    return payload


def get_pr_automerge_state(rest, owner: str, repo: str, pr_number: int) -> Tuple[bool, Optional[str]]:
    """
    Returns (is_enabled, status_string)
    status_string is informative (e.g., enabled/disabled), may be None.
    """
    # REST PR "auto_merge" is sometimes present; GraphQL is authoritative.
    query = """
    query($owner:String!, $repo:String!, $number:Int!) {
      repository(owner:$owner, name:$repo) {
        pullRequest(number:$number) {
          number
          isDraft
          autoMergeRequest { enabledAt mergeMethod }
        }
      }
    }
    """
    data = graphql(rest, query, {"owner": owner, "repo": repo, "number": pr_number})
    pr = data["data"]["repository"]["pullRequest"]
    am = pr.get("autoMergeRequest")
    if am:
        return True, f"enabled({am.get('mergeMethod')})"
    return False, "disabled"


def should_skip_pr(pr: Dict[str, Any], only_head_prefix: Optional[str], only_author: Optional[str]) -> bool:
    if pr.get("draft"):
        return True

    if only_head_prefix:
        head_ref = (pr.get("head") or {}).get("ref") or ""
        if not head_ref.startswith(only_head_prefix):
            return True

    if only_author:
        author = (pr.get("user") or {}).get("login") or ""
        if author != only_author:
            return True

    return False


def enable_automerge(rest, pr_node_id: str, merge_method: str, dry_run: bool) -> None:
    if dry_run:
        return
    graphql(rest, ENABLE_AUTOMERGE_MUTATION, {"pullRequestId": pr_node_id, "mergeMethod": merge_method})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument("--merge-method", default="SQUASH", choices=["SQUASH", "MERGE", "REBASE"])
    ap.add_argument("--max-repos", type=int, default=None)
    ap.add_argument("--max-prs-per-repo", type=int, default=None)
    ap.add_argument("--only-head-prefix", default=None, help='e.g. "autofix/"')
    ap.add_argument("--only-author", default=None, help='e.g. "dependabot[bot]"')
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--sleep-ms", type=int, default=150)
    ap.add_argument("--sleep-on-rate-limit", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    rest, _cs = create_clients()

    repos_processed = 0
    prs_seen = 0
    enabled = 0
    skipped = 0
    failed = 0

    for repo_obj in iter_repos(rest, args.owner, args.max_repos):
        repo = repo_obj.get("name")
        if not repo:
            continue
        repos_processed += 1
        full = f"{args.owner}/{repo}"
        log.info("==== %s ====", full)

        try:
            for pr in iter_open_prs(rest, args.owner, repo, args.max_prs_per_repo):
                prs_seen += 1
                number = pr.get("number")
                node_id = pr.get("node_id")
                head_ref = (pr.get("head") or {}).get("ref") or ""
                author = (pr.get("user") or {}).get("login") or ""

                if number is None or node_id is None:
                    skipped += 1
                    continue

                if should_skip_pr(pr, args.only_head_prefix, args.only_author):
                    skipped += 1
                    continue

                # Skip if already enabled (GraphQL)
                try:
                    is_enabled, status = get_pr_automerge_state(rest, args.owner, repo, int(number))
                except GitHubApiError:
                    # If GraphQL fails (rare), proceed best-effort.
                    is_enabled, status = False, None

                if is_enabled:
                    log.info("Skip %s#%s: auto-merge already %s", full, number, status or "enabled")
                    skipped += 1
                    continue

                log.info("Enable auto-merge: %s#%s (%s by %s)", full, number, head_ref, author)

                try:
                    enable_automerge(rest, node_id, args.merge_method, args.dry_run)
                    enabled += 1
                except GitHubRateLimitError as e:
                    if args.sleep_on_rate_limit and getattr(e, "reset_epoch", None):
                        reset = int(e.reset_epoch)
                        sleep_s = max(0, reset - int(time.time()))
                        log.warning("Rate limit hit; sleeping %ss then retrying once...", sleep_s)
                        time.sleep(sleep_s + 2)
                        try:
                            enable_automerge(rest, node_id, args.merge_method, args.dry_run)
                            enabled += 1
                        except Exception as e2:
                            failed += 1
                            log.warning("Failed after retry: %s#%s: %s", full, number, e2)
                    else:
                        failed += 1
                        log.warning("Rate limit error enabling auto-merge for %s#%s: %s", full, number, e)
                except (GitHubApiError, GitHubNotFoundError) as e:
                    failed += 1
                    # Common causes:
                    # - auto-merge not allowed at repo level
                    # - missing branch protection requirements
                    # - insufficient token scopes
                    log.warning("API error enabling auto-merge for %s#%s: %s", full, number, e)

                time.sleep(args.sleep_ms / 1000.0)

        except GitHubNotFoundError:
            # Repo might be inaccessible or renamed; continue.
            log.warning("Skipping repo (not found): %s", full)
            continue
        except GitHubApiError as e:
            log.warning("Skipping repo due to API error: %s (%s)", full, e)
            continue

    log.info(
        "Done. repos=%d prs_seen=%d enabled=%d skipped=%d failed=%d",
        repos_processed, prs_seen, enabled, skipped, failed
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
