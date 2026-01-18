#!/usr/bin/env python3
from __future__ import annotations
from gh_code_scanning.exceptions import GitHubNotFoundError


import argparse
import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from gh_code_scanning import create_clients
from gh_code_scanning.exceptions import GitHubApiError
from gh_code_scanning.types import Severity

ISO = "%Y-%m-%dT%H:%M:%SZ"

@dataclass(frozen=True)
class AlertRef:
    number: int
    severity: str
    created_at: str
    html_url: str
    rule_id: str

def _parse_ts(s: str) -> dt.datetime:
    return dt.datetime.strptime(s, ISO).replace(tzinfo=dt.timezone.utc)

def _age_days(created_at: str, now: dt.datetime) -> int:
    return (now - _parse_ts(created_at)).days

def upsert_issue(
    rest,
    owner: str,
    repo: str,
    title: str,
    body: str,
    labels: List[str],
) -> int:
    # Find existing open issue by exact title
    issues = rest.request(
        "GET",
        f"/repos/{owner}/{repo}/issues",
        params={"state": "open", "per_page": 100},
    ).json()

    for it in issues:
        if it.get("pull_request"):
            continue
        if it.get("title") == title:
            num = it["number"]
            rest.request(
                "PATCH",
                f"/repos/{owner}/{repo}/issues/{num}",
                json_body={"body": body, "labels": labels},
            )
            return num

    created = rest.request(
        "POST",
        f"/repos/{owner}/{repo}/issues",
        json_body={"title": title, "body": body, "labels": labels},
    ).json()
    return int(created["number"])

def main() -> int:
    ap = argparse.ArgumentParser(description="Escalate SLA-breaching code scanning alerts into GitHub Issues.")
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--sla-high-days", type=int, default=14)
    ap.add_argument("--sla-critical-days", type=int, default=7)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rest, cs = create_clients()
    now = dt.datetime.now(tz=dt.timezone.utc)

    try:
        alerts = cs.list_alerts_for_repo(args.owner, args.repo, state="open", per_page=100)
    except GitHubNotFoundError as e:
        # GitHub returns 404 "no analysis found" when code scanning has never produced results.
        msg = str(e).lower()
        if "no analysis found" in msg:
            print(f"No code scanning analysis found for {args.owner}/{args.repo}; skipping.")
            return 0
        raise


    breached: List[AlertRef] = []
    for a in alerts:
        sev = (a.get("rule", {}) or {}).get("severity") or a.get("severity")  # tolerate payload variants
        created_at = a.get("created_at")
        url = a.get("html_url") or a.get("url")
        num = int(a.get("number"))
        rule_id = (a.get("rule", {}) or {}).get("id") or "unknown"

        if not created_at or not url or not sev:
            continue

        age = _age_days(created_at, now)

        if sev == "critical" and age >= args.sla_critical_days:
            breached.append(AlertRef(num, sev, created_at, url, rule_id))
        elif sev == "high" and age >= args.sla_high_days:
            breached.append(AlertRef(num, sev, created_at, url, rule_id))

    breached.sort(key=lambda x: x.created_at)  # oldest first
    breached = breached[: max(args.top, 1)]

    if not breached:
        print("No SLA-breaching alerts found.")
        return 0

    lines = [
        f"# SLA Escalation: Code Scanning Alerts",
        "",
        f"- Repo: `{args.owner}/{args.repo}`",
        f"- Generated: `{now.isoformat()}`",
        f"- Thresholds: critical >= {args.sla_critical_days}d, high >= {args.sla_high_days}d",
        "",
        "## Oldest breaches",
        "",
        "| Age (days) | Severity | Alert # | Rule | Link |",
        "|---:|---|---:|---|---|",
    ]

    for ar in breached:
        age = _age_days(ar.created_at, now)
        lines.append(f"| {age} | {ar.severity} | {ar.number} | `{ar.rule_id}` | {ar.html_url} |")

    body = "\n".join(lines)
    title = "SLA Escalation: Code Scanning (High/Critical)"
    labels = ["security", "code-scanning", "sla-breach"]

    if args.dry_run:
        print(body)
        return 0

    issue_no = upsert_issue(rest, args.owner, args.repo, title, body, labels)
    print(f"Escalation issue updated: #{issue_no}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
