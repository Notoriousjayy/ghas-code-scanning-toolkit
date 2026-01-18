#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gh_code_scanning import create_clients
from gh_code_scanning.code_scanning_default_setup import CodeScanningDefaultSetupClient
from gh_code_scanning.exceptions import GitHubApiError, GitHubNotFoundError
from gh_code_scanning.repo_security import RepoSecurityClient

log = logging.getLogger("apply_policy")


def utcnow_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _match_regex(value: str, pattern: Optional[str]) -> bool:
    if not pattern:
        return True
    return re.search(pattern, value) is not None


def list_repos(rest, scope: Dict[str, Any]) -> List[Dict[str, Any]]:
    stype = scope.get("type")
    name = scope.get("name")
    if stype not in ("user", "org") or not name:
        raise ValueError("scope must be {'type': 'user'|'org', 'name': '<login>'}")

    repos: List[Dict[str, Any]] = []
    if stype == "user":
        # Same approach as your triage script: /user/repos filtered by owner login. :contentReference[oaicite:7]{index=7}
        params = {"affiliation": "owner", "per_page": 100, "sort": "updated", "direction": "desc"}
        for r in rest.paginate("/user/repos", params=params):
            owner = (r.get("owner") or {}).get("login") or ""
            if owner.lower() == name.lower():
                repos.append(r)
        return repos

    # org scope
    params = {"type": "all", "per_page": 100, "sort": "updated", "direction": "desc"}
    for r in rest.paginate(f"/orgs/{name}/repos", params=params):
        repos.append(r)
    return repos


@dataclass
class ApplyResult:
    full_name: str
    status: str
    details: List[str]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=".ghas-toolkit.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))

    rest, _ = create_clients()
    sec = RepoSecurityClient(rest)
    ds = CodeScanningDefaultSetupClient(rest)

    repos = list_repos(rest, cfg["scope"])
    f = cfg.get("filters") or {}

    results: List[ApplyResult] = []

    for r in repos:
        full = r.get("full_name") or ""
        if not full:
            continue

        if f.get("exclude_archived", True) and r.get("archived") is True:
            results.append(ApplyResult(full, "skipped", ["archived"]))
            continue
        if f.get("exclude_forks", True) and r.get("fork") is True:
            results.append(ApplyResult(full, "skipped", ["fork"]))
            continue

        is_private = bool(r.get("private", False))
        if is_private and not f.get("include_private", True):
            results.append(ApplyResult(full, "skipped", ["private excluded"]))
            continue
        if (not is_private) and not f.get("include_public", True):
            results.append(ApplyResult(full, "skipped", ["public excluded"]))
            continue

        if not _match_regex(full, f.get("include_regex")):
            results.append(ApplyResult(full, "skipped", ["include_regex did not match"]))
            continue
        if f.get("exclude_regex") and _match_regex(full, f.get("exclude_regex")):
            results.append(ApplyResult(full, "skipped", ["exclude_regex matched"]))
            continue

        owner, repo = full.split("/", 1)
        detail: List[str] = []

        # Apply security_and_analysis policy
        s = cfg.get("security_and_analysis") or {}
        if any(v is not None for v in s.values()):
            if args.dry_run:
                detail.append("dry-run: would set security_and_analysis")
            else:
                try:
                    sec.set_security_and_analysis(
                        owner,
                        repo,
                        advanced_security=s.get("advanced_security"),
                        code_security=s.get("code_security"),
                        secret_scanning=s.get("secret_scanning"),
                        secret_scanning_push_protection=s.get("secret_scanning_push_protection"),
                    )
                    detail.append("security_and_analysis applied")
                except GitHubApiError as e:
                    results.append(ApplyResult(full, "failed", detail + [f"security_and_analysis failed: {e}"]))
                    continue

        # Apply code scanning default setup policy
        dsc = cfg.get("code_scanning_default_setup") or {}
        if dsc.get("enabled", True):
            if args.dry_run:
                detail.append("dry-run: would configure code scanning default setup")
            else:
                try:
                    ds.configure(
                        owner,
                        repo,
                        query_suite=dsc.get("query_suite", "default"),
                        threat_model=dsc.get("threat_model", "remote_and_local"),
                        runner_type=dsc.get("runner_type", "standard"),
                        languages=dsc.get("languages"),
                    )
                    detail.append("default setup configured")
                except GitHubNotFoundError as e:
                    # some repos/endpoints may not be eligible; treat as non-fatal
                    detail.append(f"default setup not eligible/not found: {e}")
                except GitHubApiError as e:
                    results.append(ApplyResult(full, "failed", detail + [f"default setup failed: {e}"]))
                    continue

        results.append(ApplyResult(full, "ok", detail))

    # Reporting
    out = {
        "generated_at": utcnow_iso(),
        "config": cfg,
        "dry_run": bool(args.dry_run),
        "summary": {
            "ok": sum(1 for r in results if r.status == "ok"),
            "failed": sum(1 for r in results if r.status == "failed"),
            "skipped": sum(1 for r in results if r.status == "skipped"),
        },
        "results": [{"repo": r.full_name, "status": r.status, "details": r.details} for r in results],
    }

    rep = cfg.get("reporting") or {}
    write_json = rep.get("write_json")
    write_md = rep.get("write_md")

    if write_json:
        Path(write_json).parent.mkdir(parents=True, exist_ok=True)
        Path(write_json).write_text(json.dumps(out, indent=2), encoding="utf-8")
        log.info("Wrote %s", write_json)

    if write_md:
        lines = []
        lines.append(f"# GHAS Policy Apply Report ({cfg['scope']['type']}:{cfg['scope']['name']})")
        lines.append("")
        lines.append(f"- Generated: `{out['generated_at']}`")
        lines.append(f"- Dry run: `{out['dry_run']}`")
        lines.append(f"- OK: **{out['summary']['ok']}**  Failed: **{out['summary']['failed']}**  Skipped: **{out['summary']['skipped']}**")
        lines.append("")
        lines.append("| Repo | Status | Details |")
        lines.append("|---|---|---|")
        for r in results:
            lines.append(f"| `{r.full_name}` | {r.status} | {'; '.join(r.details)} |")
        Path(write_md).parent.mkdir(parents=True, exist_ok=True)
        Path(write_md).write_text("\n".join(lines), encoding="utf-8")
        log.info("Wrote %s", write_md)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
