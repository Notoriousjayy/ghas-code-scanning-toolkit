#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

from gh_code_scanning import create_clients
from gh_code_scanning.exceptions import GitHubApiError, GitHubNotFoundError


def is_no_analysis_found(err: GitHubApiError) -> bool:
    payload = getattr(err, "response_json", None) or {}
    return err.status == 404 and payload.get("message") == "no analysis found"


def list_owned_repos(rest, owner: str) -> List[str]:
    """
    Lists repos owned by the authenticated user via /user/repos.
    This avoids any gh-cli version quirks with @me, --mine, etc.
    """
    repos = []
    params = {
        "affiliation": "owner",
        "per_page": 100,
        "sort": "updated",
        "direction": "desc",
    }
    for r in rest.paginate("/user/repos", params=params):
        r_owner = (r.get("owner") or {}).get("login") or ""
        if r_owner.lower() == owner.lower():
            full_name = r.get("full_name")
            if full_name:
                repos.append(full_name)
    return repos


def render_markdown_report(
    owner: str,
    scanned: List[str],
    skipped_no_analysis: List[str],
    per_repo_counts: Dict[str, Counter],
    top_alerts: Dict[str, List[Dict[str, Any]]],
    limit_alert_rows: int = 25,
) -> str:
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    lines = []
    lines.append(f"# Code Scanning Triage Report ({owner})")
    lines.append("")
    lines.append(f"- Generated: `{now}`")
    lines.append(f"- Repos scanned: **{len(scanned)}**")
    lines.append(f"- Repos skipped (no analysis yet): **{len(skipped_no_analysis)}**")
    lines.append("")

    if skipped_no_analysis:
        lines.append("## Repos with no code scanning analysis yet")
        lines.append("")
        for r in skipped_no_analysis:
            lines.append(f"- `{r}`")
        lines.append("")

    lines.append("## Open alert counts by repo (severity)")
    lines.append("")
    lines.append("| Repo | critical | high | medium | low | warning | note | unknown | total |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    for repo in scanned:
        c = per_repo_counts.get(repo, Counter())
        total = sum(c.values())
        lines.append(
            f"| `{repo}` | {c['critical']} | {c['high']} | {c['medium']} | {c['low']} | "
            f"{c['warning']} | {c['note']} | {c['unknown']} | {total} |"
        )

    lines.append("")
    lines.append("## Top open alerts (sample)")
    lines.append("")
    lines.append("| Repo | # | severity | state | rule | tool | url |")
    lines.append("|---|---:|---|---|---|---|---|")

    added = 0
    for repo in scanned:
        for a in top_alerts.get(repo, []):
            if added >= limit_alert_rows:
                break
            rule = a.get("rule") or {}
            tool = (a.get("tool") or {}).get("name") or ""
            sev = (a.get("security_severity_level") or rule.get("severity") or "unknown")
            lines.append(
                f"| `{repo}` | {a.get('number')} | {sev} | {a.get('state')} | "
                f"{rule.get('id') or ''} | {tool} | {a.get('html_url') or ''} |"
            )
            added += 1
        if added >= limit_alert_rows:
            break

    lines.append("")
    return "\n".join(lines)


def upsert_issue(rest, owner: str, repo: str, title: str, body: str, labels: List[str]) -> None:
    """
    Creates or updates a single rolling issue that contains the latest triage report.
    Uses the Issues API via the same RestClient (request supports json_body). :contentReference[oaicite:6]{index=6}
    """
    issues = list(rest.paginate(f"/repos/{owner}/{repo}/issues", params={"state": "open", "per_page": 100}))
    existing = next((i for i in issues if i.get("title") == title), None)

    if existing:
        num = existing["number"]
        rest.request("PATCH", f"/repos/{owner}/{repo}/issues/{num}", json_body={"body": body, "labels": labels})
    else:
        rest.request("POST", f"/repos/{owner}/{repo}/issues", json_body={"title": title, "body": body, "labels": labels})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default="Notoriousjayy")
    ap.add_argument("--state", default="open")
    ap.add_argument("--write-md", default="out/code_scanning_triage.md")
    ap.add_argument("--update-issue", action="store_true")
    ap.add_argument("--issue-repo", default="Notoriousjayy/ghas-code-scanning-toolkit")
    ap.add_argument("--issue-title", default="Automated Code Scanning Triage")
    args = ap.parse_args()

    rest, cs = create_clients()

    repos = list_owned_repos(rest, args.owner)
    repos.sort()

    scanned: List[str] = []
    skipped_no_analysis: List[str] = []
    per_repo_counts: Dict[str, Counter] = {}
    top_alerts: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for full in repos:
        owner, repo = full.split("/", 1)
        try:
            alerts = cs.list_alerts_for_repo(owner, repo, state=args.state, per_page=100)
        except GitHubNotFoundError as e:
            if is_no_analysis_found(e):
                skipped_no_analysis.append(full)
                continue
            raise
        except GitHubApiError:
            raise

        scanned.append(full)
        c = Counter()
        for a in alerts:
            rule = a.get("rule") or {}
            sev = (a.get("security_severity_level") or rule.get("severity") or "unknown")
            c[str(sev).lower()] += 1

        per_repo_counts[full] = c
        top_alerts[full] = alerts[:5]

    md = render_markdown_report(args.owner, scanned, skipped_no_analysis, per_repo_counts, top_alerts)

    # write report
    import os
    os.makedirs(os.path.dirname(args.write_md), exist_ok=True)
    with open(args.write_md, "w", encoding="utf-8") as f:
        f.write(md)

    if args.update_issue:
        issue_owner, issue_repo = args.issue_repo.split("/", 1)
        upsert_issue(rest, issue_owner, issue_repo, args.issue_title, md, labels=["security", "code-scanning", "triage"])

    print(f"Wrote: {args.write_md}")
    if args.update_issue:
        print(f"Updated issue: {args.issue_repo} -> {args.issue_title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
