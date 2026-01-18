#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, List

from gh_code_scanning import create_clients
from gh_code_scanning.exceptions import GitHubApiError, GitHubNotFoundError
from gh_code_scanning.code_scanning_default_setup import CodeScanningDefaultSetupClient
from gh_code_scanning.repo_security import RepoSecurityClient

# You can import list_owned_repos from triage_all_repos if you refactor it into a module.
from triage_all_repos import list_owned_repos  # pragmatic reuse


@dataclass
class Result:
    repo: str
    status: str
    detail: str = ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", required=True)
    ap.add_argument(
        "--enable-ghas",
        action="store_true",
        help="Enable GHAS/Code Security first where possible (private repos only; public repos already have Advanced Security available).",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--query-suite", default="default", choices=["default", "extended"])
    ap.add_argument("--threat-model", default="remote_and_local", choices=["remote", "remote_and_local"])
    args = ap.parse_args()

    rest, _ = create_clients()
    ds = CodeScanningDefaultSetupClient(rest)
    sec = RepoSecurityClient(rest)

    repos = list_owned_repos(rest, args.owner)
    results: List[Result] = []

    for full in repos:
        owner, repo = full.split("/", 1)

        # Repo metadata (also used to decide whether GHAS enablement is applicable)
        try:
            repo_obj = rest.request("GET", f"/repos/{owner}/{repo}").json()

            if repo_obj.get("archived") is True:
                results.append(Result(full, "skipped", "archived"))
                continue
        except GitHubApiError as e:
            results.append(Result(full, "error", f"failed to read repo metadata: {e}"))
            continue

        is_private = bool(repo_obj.get("private", False))

        # Step 1: enable GHAS/Code Security if requested
        # - For PUBLIC repos, GitHub returns 422 ("Advanced security is always available for public repos.")
        # - For PRIVATE repos, this may be required (and can fail if you lack permissions/licensing).
        if args.enable_ghas and is_private and not args.dry_run:
            try:
                sec.set_security_and_analysis(
                    owner,
                    repo,
                    advanced_security="enabled",
                    code_security="enabled",
                )
            except GitHubApiError as e:
                results.append(Result(full, "failed", f"enable security_and_analysis failed: {e}"))
                continue

        # Step 2: configure default setup
        if args.dry_run:
            results.append(Result(full, "dry-run", "would configure default setup"))
            continue

        try:
            ds.configure(
                owner,
                repo,
                query_suite=args.query_suite,
                threat_model=args.threat_model,
                runner_type="standard",
            )
            results.append(Result(full, "configured", "default setup configured"))
        except GitHubNotFoundError as e:
            results.append(Result(full, "failed", f"default setup endpoint not found/eligible: {e}"))
        except GitHubApiError as e:
            results.append(Result(full, "failed", f"default setup failed: {e}"))

    # Print a simple summary
    counts: Dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    print("Summary:", counts)
    for r in results:
        print(f"{r.repo}: {r.status} ({r.detail})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
