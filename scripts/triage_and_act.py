#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import datetime as dt
import fnmatch
import json
import logging
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from gh_code_scanning import create_clients
from gh_code_scanning.exceptions import GitHubApiError, GitHubNotFoundError
from gh_code_scanning.types import DismissedReason

log = logging.getLogger("triage_and_act")


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def parse_gh_time(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    # GitHub typically returns Zulu timestamps; fromisoformat needs +00:00
    s = s.replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def is_no_analysis_found(err: GitHubApiError) -> bool:
    payload = getattr(err, "response_json", None) or {}
    return err.status == 404 and payload.get("message") == "no analysis found"


def list_repos(rest, scope: Dict[str, Any]) -> List[str]:
    stype = scope.get("type")
    name = scope.get("name")
    repos: List[str] = []
    if stype == "user":
        params = {"affiliation": "owner", "per_page": 100, "sort": "updated", "direction": "desc"}
        for r in rest.paginate("/user/repos", params=params):
            owner = (r.get("owner") or {}).get("login") or ""
            if owner.lower() == str(name).lower():
                if r.get("full_name"):
                    repos.append(r["full_name"])
        return sorted(repos)

    params = {"type": "all", "per_page": 100, "sort": "updated", "direction": "desc"}
    for r in rest.paginate(f"/orgs/{name}/repos", params=params):
        if r.get("full_name"):
            repos.append(r["full_name"])
    return sorted(repos)


def get_repo_file_text(rest, owner: str, repo: str, path: str, ref: Optional[str] = None) -> Optional[str]:
    params = {"ref": ref} if ref else None
    try:
        obj = rest.request("GET", f"/repos/{owner}/{repo}/contents/{path}", params=params).json()
    except GitHubNotFoundError:
        return None

    if not isinstance(obj, dict):
        return None
    if obj.get("encoding") != "base64" or "content" not in obj:
        return None

    raw = base64.b64decode(obj["content"])
    return raw.decode("utf-8", errors="replace")


def load_codeowners(rest, owner: str, repo: str, ref: Optional[str] = None) -> List[Tuple[str, List[str]]]:
    candidates = ["CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"]
    for p in candidates:
        text = get_repo_file_text(rest, owner, repo, p, ref=ref)
        if not text:
            continue
        rules: List[Tuple[str, List[str]]] = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            pattern = parts[0]
            owners = [o.strip() for o in parts[1:] if o.strip().startswith("@")]
            rules.append((pattern, owners))
        return rules
    return []


def owners_for_path(codeowners: List[Tuple[str, List[str]]], file_path: str) -> List[str]:
    # CODEOWNERS uses last-match-wins; approximate with fnmatch.
    matched: List[str] = []
    for pattern, owners in codeowners:
        if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch("/" + file_path.lstrip("/"), pattern):
            matched = owners
    # Convert @user and @org/team → try users only for assignees
    users: List[str] = []
    for o in matched:
        handle = o.lstrip("@")
        if "/" in handle:
            continue
        users.append(handle)
    return users


def should_dismiss(allow: Dict[str, Any], repo_full: str, tool_name: str, rule_id: str) -> bool:
    if allow.get("repo_regex") and re.search(allow["repo_regex"], repo_full) is None:
        return False
    if allow.get("tool_name") and allow["tool_name"] != tool_name:
        return False
    if allow.get("rule_id") and allow["rule_id"] != rule_id:
        return False
    return True


def upsert_issue(rest, owner: str, repo: str, title: str, body: str, labels: List[str]) -> None:
    issues = list(rest.paginate(f"/repos/{owner}/{repo}/issues", params={"state": "open", "per_page": 100}))
    existing = next((i for i in issues if i.get("title") == title), None)
    if existing:
        num = existing["number"]
        rest.request("PATCH", f"/repos/{owner}/{repo}/issues/{num}", json_body={"body": body, "labels": labels})
    else:
        rest.request("POST", f"/repos/{owner}/{repo}/issues", json_body={"title": title, "body": body, "labels": labels})


@dataclass
class ActionCounts:
    assigned: int = 0
    dismissed: int = 0
    escalated: int = 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", default="triage-rules.json")
    ap.add_argument("--state", default="open")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    base_dir = Path(__file__).resolve().parent
    rules_path = Path(args.rules)
    if not rules_path.is_absolute():
        rules_path = base_dir / rules_path
    rules_path = rules_path.resolve()
    try:
        # Ensure the rules file is within the base directory
        rules_path.relative_to(base_dir)
    except ValueError:
        raise ValueError(f"Rules file path '{rules_path}' is not allowed; it must be within '{base_dir}'")

    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    scope = rules["scope"]
    rest, cs = create_clients()

    repos = list_repos(rest, scope)

    per_repo_counts: Dict[str, Counter] = {}
    top_alerts: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    skipped_no_analysis: List[str] = []
    scanned: List[str] = []

    action_counts = ActionCounts()

    sla = rules.get("sla_days") or {}
    allowlist = rules.get("dismiss_allowlist") or []
    actions = rules.get("actions") or {}

    for full in repos:
        owner, repo = full.split("/", 1)

        try:
            alerts = cs.list_alerts_for_repo(owner, repo, state=args.state, per_page=100)
        except GitHubNotFoundError as e:
            if is_no_analysis_found(e):
                skipped_no_analysis.append(full)
                continue
            raise

        scanned.append(full)

        # Cache CODEOWNERS once per repo for assignment
        codeowners = load_codeowners(rest, owner, repo)

        c = Counter()
        for a in alerts:
            rule = a.get("rule") or {}
            rule_id = str(rule.get("id") or "")
            tool = (a.get("tool") or {}).get("name") or ""
            sev = (a.get("security_severity_level") or rule.get("severity") or "unknown")
            sev_l = str(sev).lower()
            c[sev_l] += 1

            # Determine age for SLA decisions
            created_at = parse_gh_time(a.get("created_at"))
            age_days = None
            if created_at:
                age_days = int((utcnow() - created_at).total_seconds() // 86400)

            # --- Auto-dismiss (allowlist only) ---
            if actions.get("auto_dismiss", {}).get("enabled") and rule_id and tool:
                for allow in allowlist:
                    if should_dismiss(allow, full, tool, rule_id):
                        if args.dry_run:
                            action_counts.dismissed += 1
                            break
                        try:
                            cs.dismiss_alert(
                                owner,
                                repo,
                                int(a["number"]),
                                reason=allow.get("reason", "false positive"),  # type: ignore[arg-type]
                                comment=allow.get("comment", "Dismissed by allowlist policy."),
                                create_request=False,
                            )
                            action_counts.dismissed += 1
                        except GitHubApiError as e:
                            log.warning("Dismiss failed %s #%s: %s", full, a.get("number"), e)
                        break

            # --- Auto-assign (CODEOWNERS) ---
            if actions.get("auto_assign", {}).get("enabled"):
                try:
                    instances = cs.list_instances(owner, repo, int(a["number"]), per_page=10)
                except GitHubApiError:
                    instances = []

                file_path = None
                for inst in instances:
                    loc = inst.get("location") or {}
                    p = loc.get("path")
                    if p:
                        file_path = str(p)
                        break

                if file_path and codeowners:
                    owners = owners_for_path(codeowners, file_path)
                    max_a = int(actions.get("auto_assign", {}).get("max_assignees", 2))
                    owners = owners[:max_a]
                    if owners:
                        if args.dry_run:
                            action_counts.assigned += 1
                        else:
                            try:
                                cs.update_alert(owner, repo, int(a["number"]), state="open", assignees=owners)
                                action_counts.assigned += 1
                            except GitHubApiError as e:
                                log.warning("Assign failed %s #%s: %s", full, a.get("number"), e)

            # --- Escalate SLA breach (issue-based) ---
            if actions.get("escalate", {}).get("enabled") and age_days is not None:
                limit = sla.get(sev_l)
                if isinstance(limit, int) and age_days >= limit:
                    action_counts.escalated += 1

        per_repo_counts[full] = c
        top_alerts[full] = alerts[:5]

    # Render markdown report
    now = utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    lines: List[str] = []
    lines.append(f"# Code Scanning Triage + Actions Report ({scope['type']}:{scope['name']})")
    lines.append("")
    lines.append(f"- Generated: `{now}`")
    lines.append(f"- Dry run: `{args.dry_run}`")
    lines.append(f"- Repos scanned: **{len(scanned)}**")
    lines.append(f"- Repos skipped (no analysis yet): **{len(skipped_no_analysis)}**")
    lines.append(f"- Actions: assigned={action_counts.assigned}, dismissed={action_counts.dismissed}, escalations={action_counts.escalated}")
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
            if added >= 25:
                break
            rule = a.get("rule") or {}
            tool = (a.get("tool") or {}).get("name") or ""
            sev = (a.get("security_severity_level") or rule.get("severity") or "unknown")
            lines.append(
                f"| `{repo}` | {a.get('number')} | {sev} | {a.get('state')} | "
                f"{rule.get('id') or ''} | {tool} | {a.get('html_url') or ''} |"
            )
            added += 1
        if added >= 25:
            break
    lines.append("")

    md = "\n".join(lines)

    rep = rules.get("reporting") or {}
    write_md = rep.get("write_md", "out/triage_actions.md")
    os.makedirs(os.path.dirname(write_md), exist_ok=True)
    Path(write_md).write_text(md, encoding="utf-8")
    log.info("Wrote %s", write_md)

    if rep.get("update_issue"):
        issue_owner, issue_repo = rep["issue_repo"].split("/", 1)
        upsert_issue(rest, issue_owner, issue_repo, rep["issue_title"], md, rep.get("issue_labels", []))
        log.info("Updated issue %s (%s)", rep["issue_repo"], rep["issue_title"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
