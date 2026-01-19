#!/usr/bin/env python3
"""
Bulk-add GitHub configuration files across repositories:
  1) .github/dependabot.yml
  2) .github/workflows/codeql.yml

This implementation intentionally avoids the Git Data API `git/trees` endpoint.
It uses:
- /languages to infer CodeQL languages
- /contents path probes (root-only) to infer dependency ecosystems

Prereqs:
- gh installed and authenticated: `gh auth status`
- Python 3.10+
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import json
import re
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple


# -----------------------------
# Models
# -----------------------------

@dataclasses.dataclass(frozen=True)
class Repo:
    owner: str
    name: str
    full_name: str
    archived: bool
    fork: bool
    private: bool


@dataclasses.dataclass(frozen=True)
class FileToApply:
    path: str
    content: str
    commit_message: str


# -----------------------------
# gh helpers
# -----------------------------

def run_cmd(args: List[str]) -> Tuple[int, str, str]:
    p = subprocess.run(args, capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def gh_json(args: List[str], allow_not_found: bool = False) -> Optional[Any]:
    rc, out, err = run_cmd(["gh"] + args)
    if rc != 0:
        if allow_not_found and ("404" in err or "Not Found" in err):
            return None
        raise RuntimeError(f"gh command failed: gh {' '.join(args)}\n{err.strip()}")
    out = out.strip()
    if not out:
        return None
    return json.loads(out)


def gh_text(args: List[str], allow_not_found: bool = False) -> Optional[str]:
    rc, out, err = run_cmd(["gh"] + args)
    if rc != 0:
        if allow_not_found and ("404" in err or "Not Found" in err):
            return None
        raise RuntimeError(f"gh command failed: gh {' '.join(args)}\n{err.strip()}")
    return out


def require_gh() -> None:
    rc, _, _ = run_cmd(["gh", "--version"])
    if rc != 0:
        raise SystemExit("ERROR: GitHub CLI `gh` not found.")
    rc, _, _ = run_cmd(["gh", "auth", "status"])
    if rc != 0:
        raise SystemExit("ERROR: `gh` is not authenticated. Run: gh auth login")


# -----------------------------
# Repo discovery
# -----------------------------

def parse_repos_csv(arg: Optional[str]) -> Optional[Set[str]]:
    if not arg:
        return None
    parts = [p.strip() for p in arg.split(",") if p.strip()]
    return set(parts) if parts else None


def list_repos(owner: str, include_archived: bool, include_forks: bool) -> List[Repo]:
    data = gh_json([
        "repo", "list", owner,
        "--limit", "1000",
        "--json", "name,nameWithOwner,isArchived,isFork,isPrivate",
    ])
    repos: List[Repo] = []
    for r in data or []:
        archived = bool(r.get("isArchived"))
        fork = bool(r.get("isFork"))
        private = bool(r.get("isPrivate"))
        if archived and not include_archived:
            continue
        if fork and not include_forks:
            continue
        full = r.get("nameWithOwner")
        name = r.get("name")
        if not full or not name:
            continue
        repos.append(Repo(owner=owner, name=name, full_name=full, archived=archived, fork=fork, private=private))
    return repos


# -----------------------------
# Repo metadata + probes
# -----------------------------

def get_default_branch(owner: str, repo: str) -> str:
    txt = gh_text(["api", f"repos/{owner}/{repo}", "--jq", ".default_branch"])
    if not txt:
        raise RuntimeError(f"Unable to determine default branch for {owner}/{repo}")
    return txt.strip()


def get_repo_languages(owner: str, repo: str) -> Dict[str, int]:
    j = gh_json(["api", f"repos/{owner}/{repo}/languages"], allow_not_found=True)
    return dict(j or {})


def repo_has_path(owner: str, repo: str, path: str, ref: str) -> bool:
    j = gh_json(["api", f"repos/{owner}/{repo}/contents/{path}", "-f", f"ref={ref}"], allow_not_found=True)
    return j is not None


# -----------------------------
# Detection logic (robust mode)
# -----------------------------

LANG_TO_CODEQL: Dict[str, str] = {
    "JavaScript": "javascript-typescript",
    "TypeScript": "javascript-typescript",
    "Python": "python",
    "Java": "java-kotlin",
    "Kotlin": "java-kotlin",
    "C": "c-cpp",
    "C++": "c-cpp",
    "C#": "csharp",
    "Go": "go",
    "Ruby": "ruby",
    "Swift": "swift",
}

CODEQL_ORDER = ["javascript-typescript", "python", "java-kotlin", "c-cpp", "csharp", "go", "ruby", "swift"]


def detect_codeql_languages_from_languages_api(lang_map: Dict[str, int]) -> List[str]:
    found: Set[str] = set()
    for lang_name in (lang_map or {}).keys():
        codeql = LANG_TO_CODEQL.get(lang_name)
        if codeql:
            found.add(codeql)
    return [l for l in CODEQL_ORDER if l in found]


def detect_dependabot_updates_root_only(owner: str, repo: str, ref: str) -> Dict[str, List[str]]:
    """
    Conservative detection: root-level manifests + always GitHub Actions.
    """
    updates: Dict[str, List[str]] = {"github-actions": ["/"]}

    if repo_has_path(owner, repo, "package.json", ref):
        updates.setdefault("npm", []).append("/")

    if any(repo_has_path(owner, repo, p, ref) for p in ["requirements.txt", "pyproject.toml", "Pipfile", "setup.py"]):
        updates.setdefault("pip", []).append("/")

    if repo_has_path(owner, repo, "pom.xml", ref):
        updates.setdefault("maven", []).append("/")

    if any(repo_has_path(owner, repo, p, ref) for p in ["build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"]):
        updates.setdefault("gradle", []).append("/")

    if repo_has_path(owner, repo, "go.mod", ref):
        updates.setdefault("gomod", []).append("/")

    if repo_has_path(owner, repo, "Cargo.toml", ref):
        updates.setdefault("cargo", []).append("/")

    if repo_has_path(owner, repo, "composer.json", ref):
        updates.setdefault("composer", []).append("/")

    if repo_has_path(owner, repo, "Gemfile", ref):
        updates.setdefault("bundler", []).append("/")

    if repo_has_path(owner, repo, "pubspec.yaml", ref):
        updates.setdefault("pub", []).append("/")

    if repo_has_path(owner, repo, "Dockerfile", ref):
        updates.setdefault("docker", []).append("/")

    # NuGet (root listing best-effort)
    root_listing = gh_json(["api", f"repos/{owner}/{repo}/contents", "-f", f"ref={ref}"], allow_not_found=True)
    if isinstance(root_listing, list):
        for entry in root_listing:
            name = str(entry.get("name", ""))
            if re.search(r"\.(csproj|fsproj|vbproj|vcxproj|nuspec)$", name, flags=re.IGNORECASE) or name.lower() == "packages.config":
                updates.setdefault("nuget", []).append("/")
                break

    preferred = [
        "github-actions", "npm", "pip", "maven", "gradle", "gomod", "cargo",
        "nuget", "composer", "bundler", "pub", "docker",
    ]
    ordered: Dict[str, List[str]] = {}
    for eco in preferred:
        if eco in updates:
            ordered[eco] = sorted(set(updates[eco]))
    return ordered


# -----------------------------
# Renderers
# -----------------------------

def render_dependabot_yml(update_dirs: Dict[str, List[str]], interval: str, open_pr_limit: int) -> str:
    lines: List[str] = ["version: 2", "updates:"]

    def add_update(ecosystem: str, directory: str) -> None:
        lines.append(f'  - package-ecosystem: "{ecosystem}"')
        lines.append(f'    directory: "{directory}"')
        lines.append("    schedule:")
        lines.append(f'      interval: "{interval}"')
        lines.append("    labels:")
        lines.append('      - "dependencies"')
        lines.append(f"    open-pull-requests-limit: {open_pr_limit}")

    for eco, dirs in update_dirs.items():
        for d in dirs:
            add_update(eco, d)

    return "\n".join(lines) + "\n"


def render_codeql_workflow_yml(default_branch: str, languages: List[str]) -> str:
    # Manual-only if we cannot infer languages (avoids noisy failures on push/PR)
    if not languages:
        return """name: CodeQL

on:
  workflow_dispatch:

permissions:
  contents: read
  security-events: write

jobs:
  analyze:
    name: Analyze (manual)
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: javascript-typescript
      - name: Autobuild
        uses: github/codeql-action/autobuild@v3
      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
"""

    langs_yaml = "\n".join([f"          - {l}" for l in languages])

    # NOTE: f-string needs doubled braces to emit ${{ matrix.language }}
    return f"""name: CodeQL

on:
  push:
    branches:
      - {default_branch}
  pull_request:
    branches:
      - {default_branch}
  schedule:
    - cron: "30 5 * * 1"

permissions:
  contents: read
  security-events: write

jobs:
  analyze:
    name: Analyze
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        language:
{langs_yaml}

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Initialize CodeQL
        uses: github/codeql-action/init@v3
        with:
          languages: ${{{{ matrix.language }}}}

      - name: Autobuild
        uses: github/codeql-action/autobuild@v3

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
"""


# -----------------------------
# Contents API operations
# -----------------------------

def get_file_sha(owner: str, repo: str, path: str, ref: str) -> Optional[str]:
    j = gh_json(["api", f"repos/{owner}/{repo}/contents/{path}", "-f", f"ref={ref}"], allow_not_found=True)
    if not j:
        return None
    return j.get("sha")


def put_file(
    owner: str,
    repo: str,
    path: str,
    content_utf8: str,
    message: str,
    branch: str,
    sha_if_update: Optional[str],
    dry_run: bool,
) -> None:
    b64 = base64.b64encode(content_utf8.encode("utf-8")).decode("ascii")
    args = ["api", "--method", "PUT", f"repos/{owner}/{repo}/contents/{path}"]
    args += ["-f", f"message={message}", "-f", f"content={b64}", "-f", f"branch={branch}"]
    if sha_if_update:
        args += ["-f", f"sha={sha_if_update}"]

    if dry_run:
        print(f"    DRY-RUN: would PUT {path} on branch {branch} (update={bool(sha_if_update)})")
        return

    gh_json(args)


def get_head_commit_sha(owner: str, repo: str, branch: str) -> str:
    j = gh_json(["api", f"repos/{owner}/{repo}/git/ref/heads/{branch}"])
    sha = (j or {}).get("object", {}).get("sha")
    if not sha:
        raise RuntimeError(f"Unable to get head SHA for {owner}/{repo}@{branch}")
    return sha


def create_branch(owner: str, repo: str, new_branch: str, base_branch: str, dry_run: bool) -> None:
    base_sha = get_head_commit_sha(owner, repo, base_branch)

    existing = gh_json(["api", f"repos/{owner}/{repo}/git/ref/heads/{new_branch}"], allow_not_found=True)
    if existing:
        return

    if dry_run:
        print(f"    DRY-RUN: would create branch {new_branch} from {base_branch} ({base_sha[:7]})")
        return

    gh_json([
        "api", "--method", "POST",
        f"repos/{owner}/{repo}/git/refs",
        "-f", f"ref=refs/heads/{new_branch}",
        "-f", f"sha={base_sha}",
    ])


def create_pull_request(owner: str, repo: str, head_branch: str, base_branch: str, title: str, body: str, dry_run: bool) -> None:
    # In dry-run, never call the network for PR detection/creation.
    if dry_run:
        print(f"    DRY-RUN: would open PR {head_branch} -> {base_branch}")
        return

    # Avoid /search/issues. Just attempt PR creation and treat "already exists" as a no-op.
    try:
        gh_json([
            "api", "--method", "POST",
            f"repos/{owner}/{repo}/pulls",
            "-f", f"title={title}",
            "-f", f"head={owner}:{head_branch}",
            "-f", f"base={base_branch}",
            "-f", f"body={body}",
        ])
    except RuntimeError as e:
        msg = str(e)
        # Common GitHub response when a PR already exists for the same head/base.
        if ("HTTP 422" in msg) and ("already exists" in msg.lower() or "pull request" in msg.lower()):
            return
        raise


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Bulk add Dependabot + CodeQL config files to GitHub repos.")
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repos", default=None, help="Comma-separated list owner/name,owner/name")
    ap.add_argument("--include-archived", action="store_true")
    ap.add_argument("--include-forks", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--mode", choices=["pr", "commit"], default="pr")
    ap.add_argument("--branch-prefix", default="automation/dependabot-codeql")
    ap.add_argument("--dry-run", action="store_true")

    ap.add_argument("--dependabot-interval", choices=["daily", "weekly", "monthly"], default="weekly")
    ap.add_argument("--dependabot-open-pr-limit", type=int, default=10)

    args = ap.parse_args()

    require_gh()

    owner = args.owner
    limit_set = parse_repos_csv(args.repos)

    repos = list_repos(owner, include_archived=args.include_archived, include_forks=args.include_forks)
    if limit_set is not None:
        repos = [r for r in repos if r.full_name in limit_set]

    if not repos:
        print("No repositories matched your filters.")
        return 0

    today = datetime.utcnow().strftime("%Y%m%d")

    print(f"Target owner: {owner}")
    print(f"Repositories: {len(repos)}")
    print(f"Mode: {args.mode}  Dry-run: {args.dry_run}")
    print("")

    for idx, r in enumerate(repos, start=1):
        print(f"[{idx}/{len(repos)}] {r.full_name}")

        try:
            default_branch = get_default_branch(owner, r.name)

            lang_map = get_repo_languages(owner, r.name)
            codeql_langs = detect_codeql_languages_from_languages_api(lang_map)

            dep_updates = detect_dependabot_updates_root_only(owner, r.name, default_branch)

            dependabot_yml = render_dependabot_yml(dep_updates, args.dependabot_interval, args.dependabot_open_pr_limit)
            codeql_yml = render_codeql_workflow_yml(default_branch, codeql_langs)

            files: List[FileToApply] = [
                FileToApply(".github/dependabot.yml", dependabot_yml, "chore: add Dependabot config"),
                FileToApply(".github/workflows/codeql.yml", codeql_yml, "chore: add CodeQL workflow"),
            ]

            if args.mode == "pr":
                pr_branch = f"{args.branch_prefix}/{today}"
                create_branch(owner, r.name, pr_branch, default_branch, args.dry_run)
                target_branch = pr_branch
            else:
                target_branch = default_branch

            changed_any = False
            for f in files:
                sha = get_file_sha(owner, r.name, f.path, ref=target_branch)
                if sha is None and target_branch != default_branch:
                    # Fallback: look up sha on the base branch (PR branch starts from base)
                    sha = get_file_sha(owner, r.name, f.path, ref=default_branch)
                if sha and not args.overwrite:
                    print(f"    SKIP: {f.path} already exists (use --overwrite to replace)")
                    continue

                put_file(
                    owner=owner,
                    repo=r.name,
                    path=f.path,
                    content_utf8=f.content,
                    message=f.commit_message,
                    branch=target_branch,
                    sha_if_update=sha,
                    dry_run=args.dry_run,
                )
                changed_any = True
                print(f"    {'UPDATED' if sha else 'CREATED'}: {f.path}")

            if args.mode == "pr" and changed_any:
                create_pull_request(
                    owner, r.name,
                    head_branch=target_branch,
                    base_branch=default_branch,
                    title="chore: add Dependabot + CodeQL configuration",
                    body=(
                        "This PR adds baseline security automation:\n"
                        "- .github/dependabot.yml\n"
                        "- .github/workflows/codeql.yml\n"
                    ),
                    dry_run=args.dry_run,
                )
                print(f"    PR: {target_branch} -> {default_branch}")

        except Exception as e:
            print(f"    ERROR: {e}")

        print("")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
