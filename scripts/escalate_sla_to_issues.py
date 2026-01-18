#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import logging
from typing import Any, Dict, List, Optional

from gh_code_scanning import create_clients
from gh_code_scanning.exceptions import GitHubApiError, GitHubNotFoundError

log = logging.getLogger("escalate_sla_to_issues")


def parse_iso8601(s: str) -> dt.datetime:
    # GitHub timestamps are typically like "2026-01-18T23:08:17Z"
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def severity_of(alert: Dict[str, Any]) -> str:
    rule = alert.get("rule") or {}
    sev = (
        alert.get("security_severity_level")
        or rule.get("security_severity_level")
        or rule.get("severity")
        or alert.get("severity")
        or "unknown"
    )
    return str(sev).strip().lower()


def created_at_of(alert: Dict[str, Any]) -> Optional[dt.datetime]:
    raw = alert.get("created_at")
    if raw:
        try:
            return parse_iso8601(str(raw))
        except Exception:
            return None
    return None


def build_issue_body(owner: str, repo: str, breaches: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("# SLA Escalation: Code Scanning (High/Critical)")
    lines.append("")
    lines.append(f"Repository: `{owner}/{repo}`")
    lines.append(f"Generated: `{utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}`")
    lines.append("")
    lines.append("## Breaching alerts")
    lines.append("")
    lines.append("| Severity | Alert | Created | Age (days) |")
    lines.append("|---|---:|---|---:|")
    for b in breaches:
        sev = b["severity"]
        num = b["number"]
        url = b.get("html_url") or ""
        created = b.get("created_at") or ""
        age = b["age_days"]
        lines.append(f"| `{sev}` | [{num}]({url}) | `{created}` | `{age:.2f}` |")
    lines.append("")
    return "\n".join(lines)


def upsert_issue(rest, owner: str, repo: str, title: str, body: str) -> None:
    # Find existing open issue with exact title
    issues = rest.request(
        "GET",
        f"/repos/{owner}/{repo}/issues",
        params={"state": "open", "per_page": 100},
    ).json()

    existing = None
    if isinstance(issues, list):
        for it in issues:
            if isinstance(it, dict) and it.get("title") == title and "pull_request" not in it:
                existing = it
                break

    if existing:
        num = existing["number"]
        rest.request(
            "PATCH",
            f"/repos/{owner}/{repo}/issues/{num}",
            json_body={"body": body},
        )
        log.info("Updated issue #%s: %s", num, existing.get("html_url"))
        return

    created = rest.request(
        "POST",
        f"/repos/{owner}/{repo}/issues",
        json_body={"title": title, "body": body},
    ).json()
    log.info("Created issue: %s", created.get("html_url"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Escalate code scanning alerts that breach SLA to a GitHub issue.")
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--sla-critical-days", type=float, default=7.0)
    ap.add_argument("--sla-high-days", type=float, default=14.0)
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    rest, cs = create_clients()

    try:
        alerts = cs.list_alerts_for_repo(args.owner, args.repo, state="open", per_page=100)
    except GitHubNotFoundError as e:
        if "no analysis found" in str(e).lower():
            print(f"No code scanning analysis found for {args.owner}/{args.repo}; skipping.")
            return 0
        raise

    now = utcnow()
    breaches: List[Dict[str, Any]] = []

    for a in alerts:
        sev = severity_of(a)
        if sev not in ("critical", "high"):
            continue

        created_dt = created_at_of(a)
        if not created_dt:
            continue

        age_days = (now - created_dt).total_seconds() / 86400.0
        threshold = args.sla_critical_days if sev == "critical" else args.sla_high_days

        if age_days >= threshold:
            breaches.append(
                {
                    "severity": sev,
                    "number": int(a["number"]),
                    "html_url": a.get("html_url"),
                    "created_at": a.get("created_at"),
                    "age_days": age_days,
                }
            )

    breaches.sort(key=lambda x: (0 if x["severity"] == "critical" else 1, -x["age_days"]))

    if not breaches:
        print("No SLA-breaching alerts found.")
        return 0

    breaches = breaches[: args.top]
    title = "SLA Escalation: Code Scanning (High/Critical)"
    body = build_issue_body(args.owner, args.repo, breaches)

    if args.dry_run:
        print(body)
        return 0

    try:
        upsert_issue(rest, args.owner, args.repo, title=title, body=body)
    except GitHubApiError as e:
        log.error("Failed to create/update issue: %s", e)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
