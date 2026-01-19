#!/usr/bin/env python3
"""
Bulk-apply GitHub repository configuration files across many repositories.

Supports bundles:
  --include ghas            (Dependabot, CodeQL workflow/config, dependency review workflow/config, qlpack)
  --include community       (CONTRIBUTING, CODE_OF_CONDUCT, CITATION, SECURITY, SUPPORT, FUNDING, USAGE, HELP, CODEOWNERS, etc.)
  --include collaboration   (Issue templates/forms + config, PR template, discussion templates)
  --include actions         (Reusable workflows, composite action stubs, workflow starter templates for org .github repo)
  --include release         (release.yml config, release request form, helper workflow to view latest release)
  --include readmes         (profile README for <owner>/<owner>, org profile README for <owner>/.github)
  --include all

Behavior:
  - If a file already exists: SKIP by default (no failure).
  - Use --update-existing to overwrite existing files (sha-aware updates).
  - --mode pr creates a branch and opens PRs.
  - --dry-run prints planned actions.

Prereqs:
  - gh installed and authenticated (gh auth status)
  - Python 3.10+
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import json
import subprocess
import time
import random
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
import re
_TREE_SHA_CACHE: Dict[Tuple[str, str, str], Dict[str, str]] = {}

# -----------------------------
# Base64 helper
# -----------------------------

def b64(content: str | bytes) -> str:
    """Return GitHub Contents API-compatible base64 for UTF-8 text."""
    if isinstance(content, bytes):
        data = content
    else:
        data = content.encode("utf-8")
    return base64.b64encode(data).decode("ascii")


def build_branch_name() -> str:
    """Generate default branch name: automation/github-configs/YYYYMMDD."""
    today = datetime.now().strftime("%Y%m%d")
    return f"automation/github-configs/{today}"


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
    default_branch: Optional[str] = None


@dataclasses.dataclass(frozen=True)
class FileToApply:
    path: str
    content: str
    commit_message: str


# -----------------------------
# gh helpers
# -----------------------------

def _sleep_backoff(attempt: int, base: float) -> None:
    """Exponential backoff with jitter."""
    delay = base * (2 ** attempt)
    jitter = delay * 0.1
    time.sleep(delay + (random.random() * jitter))


def run_cmd(args: Sequence[str]) -> Tuple[int, str, str]:
    p = subprocess.run(list(args), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def gh_json(args: List[str], allow_not_found: bool = False, *, max_retries: int = 3, backoff_base: float = 0.75) -> Any:
    """Run `gh ...` and parse JSON, with basic retries on transient failures."""
    cmd = ["gh"] + args

    for attempt in range(max_retries + 1):
        rc, out, err = run_cmd(cmd)
        err = (err or "").strip()

        if rc == 0:
            if not out.strip():
                return None
            return json.loads(out)

        if allow_not_found and ("HTTP 404" in err or "Not Found" in err):
            return None

        transient_markers = (
            "HTTP 500",
            "HTTP 502",
            "HTTP 503",
            "HTTP 504",
            "Bad Gateway",
            "Service Unavailable",
            "Gateway Timeout",
            "timeout",
            "timed out",
            "Temporary failure",
            "Connection reset",
            "EOF",
            "TLS",
            "secondary rate limit",
            "abuse detection",
        )

        is_transient = any(m in err for m in transient_markers)
        if is_transient and attempt < max_retries:
            _sleep_backoff(attempt, backoff_base)
            continue

        raise RuntimeError(f"gh command failed ({rc}): {' '.join(cmd)}\n{err}")

    raise RuntimeError(f"gh command failed (exhausted retries): {' '.join(cmd)}")
def gh_text(args: List[str], allow_not_found: bool = False) -> Optional[str]:
    rc, out, err = run_cmd(["gh"] + args)
    if rc != 0:
        if allow_not_found and ("404" in err or "Not Found" in err):
            return None
        raise RuntimeError(f"gh command failed ({rc}): gh {' '.join(args)}\n{err.strip()}")
    return out


def require_gh() -> None:
    rc, _, _ = run_cmd(["gh", "--version"])
    if rc != 0:
        raise SystemExit("ERROR: GitHub CLI `gh` not found.")
    rc, _, _ = run_cmd(["gh", "auth", "status"])
    if rc != 0:
        raise SystemExit("ERROR: `gh` is not authenticated. Run: gh auth login")


# -----------------------------
# Repo discovery (fixes your 404)
# -----------------------------

def parse_repos_csv(arg: Optional[str]) -> Optional[Set[str]]:
    if not arg:
        return None
    parts = [p.strip() for p in arg.split(",") if p.strip()]
    return set(parts) if parts else None


def list_repos(owner: str, include_archived: bool, include_forks: bool) -> List[Repo]:
    # Use `gh repo list` (works for user/org; includes private repos you can see)
    data = gh_json([
        "repo", "list", owner,
        "--limit", "1000",
        "--json", "name,nameWithOwner,isArchived,isFork,isPrivate,defaultBranchRef",
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
        default_branch = None
        dbr = r.get("defaultBranchRef") or {}
        if isinstance(dbr, dict):
            default_branch = dbr.get("name")
        if not full or not name:
            continue
        repos.append(Repo(owner=owner, name=name, full_name=full, archived=archived, fork=fork, private=private, default_branch=default_branch))
    return repos


def get_default_branch(owner: str, repo: str, hinted: Optional[str]) -> str:
    if hinted:
        return hinted
    txt = gh_text(["api", f"repos/{owner}/{repo}", "--jq", ".default_branch"])
    if not txt:
        raise RuntimeError(f"Unable to determine default branch for {owner}/{repo}")
    return txt.strip()


# -----------------------------
# Contents API operations
# -----------------------------

def get_file_obj(owner: str, repo: str, path: str, ref: str) -> Optional[Dict[str, Any]]:
    j = gh_json(["api", f"repos/{owner}/{repo}/contents/{path}", "-f", f"ref={ref}"], allow_not_found=True)
    if not isinstance(j, dict):
        return None
    return j


def _normalize_repo_path(path: str) -> str:
    # GitHub Contents API expects paths without leading "/" and without "./"
    p = path.strip()
    while p.startswith("/"):
        p = p[1:]
    if p.startswith("./"):
        p = p[2:]
    return p


def _get_commit_sha_for_ref(owner: str, repo: str, ref: str) -> Optional[str]:
    # ref is expected to be a branch name (often with slashes).
    # If a raw 40-hex commit SHA is provided, accept it directly.
    if re.fullmatch(r"[0-9a-f]{40}", ref):
        return ref

    j = gh_json(["api", f"repos/{owner}/{repo}/git/ref/heads/{ref}"], allow_not_found=True)
    if not j or not isinstance(j, dict):
        return None
    obj = j.get("object") or {}
    sha = obj.get("sha")
    return sha if isinstance(sha, str) and sha else None


def _build_tree_sha_map(owner: str, repo: str, ref: str) -> Optional[Dict[str, str]]:
    key = (owner, repo, ref)
    if key in _TREE_SHA_CACHE:
        return _TREE_SHA_CACHE[key]

    commit_sha = _get_commit_sha_for_ref(owner, repo, ref)
    if not commit_sha:
        return None

    commit = gh_json(["api", f"repos/{owner}/{repo}/git/commits/{commit_sha}"], allow_not_found=True)
    if not commit or not isinstance(commit, dict):
        return None

    tree_obj = commit.get("tree") or {}
    tree_sha = tree_obj.get("sha")
    if not isinstance(tree_sha, str) or not tree_sha:
        return None

    tree = gh_json(["api", f"repos/{owner}/{repo}/git/trees/{tree_sha}", "-f", "recursive=1"], allow_not_found=True)
    if not tree or not isinstance(tree, dict):
        return None

    out: Dict[str, str] = {}
    for entry in tree.get("tree", []) or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("type") != "blob":
            continue
        p = entry.get("path")
        s = entry.get("sha")
        if isinstance(p, str) and isinstance(s, str):
            out[p] = s

    _TREE_SHA_CACHE[key] = out
    return out


def get_file_sha(owner: str, repo: str, path: str, ref: str, *, use_tree_fallback: bool = False) -> Optional[str]:
    """Resolve blob SHA for a file at `path` in `ref`.

    Primary: Contents API.
    Fallback (opt-in): tree walk via Git data endpoints when the Contents API fails unexpectedly.
    """
    norm_path = _normalize_repo_path(path)

    obj = get_file_obj(owner, repo, norm_path, ref)
    if obj and isinstance(obj, dict):
        sha = obj.get("sha")
        if isinstance(sha, str) and sha:
            return sha

    if not use_tree_fallback:
        return None

    tree_map = _build_tree_sha_map(owner, repo, ref)
    if not tree_map:
        return None
    return tree_map.get(norm_path)

def get_file_text(owner: str, repo: str, path: str, ref: str) -> Optional[str]:
    obj = get_file_obj(owner, repo, path, ref)
    if not obj:
        return None
    if obj.get("encoding") != "base64" or "content" not in obj:
        return None
    raw = base64.b64decode(obj["content"])
    return raw.decode("utf-8", errors="replace")


def put_file(
    owner: str,
    repo: str,
    path: str,
    content: str,
    message: str,
    branch: str,
    sha_if_update: Optional[str],
    *,
    update_if_exists: bool,
    dry_run: bool = False,
) -> bool:
    """Create or update a repository file via the Contents API.

    Returns True if a commit was (or would be) created; False if skipped because the file already exists and
    `update_if_exists` is False.

    Notes:
    - GitHub requires `sha` when updating an existing file.
    - We attempt a create first when `sha_if_update` is None.
    - On 422/"sha wasn't supplied", we either:
        * skip (if update_if_exists is False), or
        * resolve the SHA (Contents API, then tree fallback) and retry (if update_if_exists is True).
    """
    norm_path = _normalize_repo_path(path)

    if dry_run:
        return True

    args = [
        "api",
        "--method",
        "PUT",
        f"repos/{owner}/{repo}/contents/{norm_path}",
        "-f",
        f"message={message}",
        "-f",
        f"content={b64(content)}",
        "-f",
        f"branch={branch}",
    ]
    if sha_if_update:
        args.extend(["-f", f"sha={sha_if_update}"])

    try:
        gh_json(args)
        return True
    except RuntimeError as e:
        msg = str(e)
        if "HTTP 422" in msg and "sha" in msg and "wasn't supplied" in msg:
            if not update_if_exists:
                print(f"    SKIP(existing): {norm_path}")
                return False

            sha = sha_if_update or get_file_sha(owner, repo, norm_path, branch, use_tree_fallback=True)
            if not sha:
                sha = get_file_sha(owner, repo, norm_path, get_default_branch(owner, repo, None), use_tree_fallback=True)
            if not sha:
                raise

            args2 = args.copy()
            if not any(a.startswith("sha=") for a in args2):
                args2.extend(["-f", f"sha={sha}"])
            gh_json(args2)
            return True

        raise

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
    if dry_run:
        print(f"    DRY-RUN: would open PR {head_branch} -> {base_branch}")
        return

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
        msg = str(e).lower()
        # PR already exists for same head/base
        if "http 422" in msg and ("already exists" in msg or "pull request" in msg):
            return
        raise


# -----------------------------
# Probes
# -----------------------------

def repo_has_path(owner: str, repo: str, path: str, ref: str) -> bool:
    j = gh_json(["api", f"repos/{owner}/{repo}/contents/{path}", "-f", f"ref={ref}"], allow_not_found=True)
    return j is not None


def infer_dependabot_ecosystems(owner: str, repo: str, ref: str) -> Dict[str, List[str]]:
    """
    Conservative: root-only probes (fast, avoids tree API).
    Returns map ecosystem -> list of directories.
    """
    eco: Dict[str, List[str]] = {}

    def add(e: str, d: str = "/") -> None:
        eco.setdefault(e, [])
        if d not in eco[e]:
            eco[e].append(d)

    # GitHub Actions
    if repo_has_path(owner, repo, ".github/workflows", ref):
        add("github-actions", "/")

    # npm
    if repo_has_path(owner, repo, "package.json", ref):
        add("npm", "/")

    # pip
    if (repo_has_path(owner, repo, "requirements.txt", ref) or
        repo_has_path(owner, repo, "pyproject.toml", ref) or
        repo_has_path(owner, repo, "Pipfile", ref) or
        repo_has_path(owner, repo, "setup.py", ref)):
        add("pip", "/")

    # Maven / Gradle
    if repo_has_path(owner, repo, "pom.xml", ref):
        add("maven", "/")
    if repo_has_path(owner, repo, "build.gradle", ref) or repo_has_path(owner, repo, "build.gradle.kts", ref):
        add("gradle", "/")

    # Go
    if repo_has_path(owner, repo, "go.mod", ref):
        add("gomod", "/")

    # Rust
    if repo_has_path(owner, repo, "Cargo.toml", ref):
        add("cargo", "/")

    # NuGet
    if repo_has_path(owner, repo, "packages.config", ref):
        add("nuget", "/")

    # Composer
    if repo_has_path(owner, repo, "composer.json", ref):
        add("composer", "/")

    # Bundler
    if repo_has_path(owner, repo, "Gemfile", ref):
        add("bundler", "/")

    # Pub
    if repo_has_path(owner, repo, "pubspec.yaml", ref):
        add("pub", "/")

    return eco


def get_repo_languages(owner: str, repo: str) -> Dict[str, int]:
    j = gh_json(["api", f"repos/{owner}/{repo}/languages"], allow_not_found=True)
    return dict(j or {})


def infer_codeql_languages(lang_bytes: Dict[str, int]) -> List[str]:
    # Map GitHub language names to CodeQL language ids
    langset = set(lang_bytes.keys())

    out: List[str] = []
    def add(x: str) -> None:
        if x not in out:
            out.append(x)

    if "JavaScript" in langset or "TypeScript" in langset:
        add("javascript-typescript")
    if "Python" in langset:
        add("python")
    if "Go" in langset:
        add("go")
    if "Java" in langset or "Kotlin" in langset:
        add("java-kotlin")
    if "C" in langset or "C++" in langset:
        add("c-cpp")
    if "C#" in langset:
        add("csharp")
    if "Ruby" in langset:
        add("ruby")
    if "Swift" in langset:
        add("swift")

    return out


# -----------------------------
# Renderers (GHAS)
# -----------------------------

def render_dependabot_yml(update_dirs: Dict[str, List[str]], interval: str, open_pr_limit: int) -> str:
    lines: List[str] = ["version: 2"]

    # Optional registries section (commented example)
    lines += [
        "",
        "# registries:",
        "#   my-private-registry:",
        "#     type: npm-registry",
        "#     url: https://registry.npmjs.org",
        "#     token: ${{ secrets.DEPENDABOT_TOKEN }}",
        "",
        "updates:",
    ]

    def add_update(ecosystem: str, directory: str) -> None:
        lines.append(f'  - package-ecosystem: "{ecosystem}"')
        lines.append(f'    directory: "{directory}"')
        lines.append("    schedule:")
        lines.append(f'      interval: "{interval}"')
        lines.append("    labels:")
        lines.append('      - "dependencies"')
        lines.append(f"    open-pull-requests-limit: {open_pr_limit}")

    for eco, dirs in sorted(update_dirs.items()):
        for d in sorted(dirs):
            add_update(eco, d)

    return "\n".join(lines) + "\n"


def render_dependency_review_workflow_yml() -> str:
    return """name: Dependency Review

on:
  pull_request:

permissions:
  contents: read

jobs:
  dependency-review:
    name: dependency-review
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Dependency Review
        uses: actions/dependency-review-action@v4
        with:
          config-file: .github/dependency-review-config.yml

      - name: Summary
        if: always()
        run: |
          {
            echo "## Dependency Review"
            echo ""
            echo "- Workflow: $GITHUB_WORKFLOW"
            echo "- Run: $GITHUB_RUN_ID"
            echo "- Ref: $GITHUB_REF"
          } >> "$GITHUB_STEP_SUMMARY"
"""


def render_dependency_review_config_yml() -> str:
    # Minimal, safe defaults. Adjust to your policy.
    return """fail-on-severity: moderate
allow-licenses:
  - MIT
  - Apache-2.0
  - BSD-2-Clause
  - BSD-3-Clause
deny-licenses:
  - AGPL-3.0
comment-summary-in-pr: true
"""


def render_codeql_config_yml() -> str:
    return """name: "CodeQL config"
queries:
  - uses: security-and-quality
paths-ignore:
  - "**/dist/**"
  - "**/build/**"
  - "**/vendor/**"
  - "**/node_modules/**"
"""


def render_qlpack_yml(owner: str, repo: str) -> str:
    # Not referenced by default; provided as a starting point for custom query packs.
    # Keep it harmless unless you wire it into CodeQL config.
    return f"""name: {owner}/{repo}-codeql-pack
version: 0.0.1
library: true
dependencies: {{}}
"""


def render_codeql_workflow_yml(default_branch: str, languages: List[str]) -> str:
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
    # Double braces to emit ${{ matrix.language }}
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
          config-file: .github/codeql/codeql-config.yml

      - name: Autobuild
        uses: github/codeql-action/autobuild@v3

      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@v3
"""


# -----------------------------
# Renderers (Community / Collaboration / Release / Readmes)
# -----------------------------

def render_contributing_md(owner: str, repo: str) -> str:
    return f"""# Contributing to {repo}

Thanks for your interest in contributing.

## How to contribute
1. Open an Issue describing the problem or feature request.
2. Fork the repository and create a feature branch.
3. Keep changes focused and add tests when applicable.
4. Submit a Pull Request referencing the Issue.

## Development standards
- Follow the existing style and tooling in the repository.
- Prefer small, reviewable PRs.
- Document user-facing changes in the README or docs.

## Security
If you believe you have found a security issue, please follow SECURITY.md.
"""


def render_code_of_conduct_md() -> str:
    return """# Code of Conduct

This project follows the Contributor Covenant Code of Conduct.

## Our pledge
We pledge to make participation in our community a harassment-free experience for everyone.

## Enforcement
Report unacceptable behavior via the contact method in SUPPORT.md or SECURITY.md (if security-related).

## Attribution
Contributor Covenant: https://www.contributor-covenant.org/
"""


def render_citation_cff(owner: str, repo: str) -> str:
    today = datetime.utcnow().date().isoformat()
    return f"""cff-version: 1.2.0
message: "If you use this software, please cite it."
title: "{repo}"
type: software
authors:
  - name: "{owner}"
date-released: "{today}"
url: "https://github.com/{owner}/{repo}"
"""


def render_security_md(owner: str) -> str:
    return f"""# Security Policy

## Supported versions
Security updates are provided for the latest release (or default branch if no releases exist).

## Reporting a vulnerability
Please do not open public issues for security vulnerabilities.

Instead:
1. Contact the maintainer: @{owner}
2. Provide a clear description, steps to reproduce, and impact.
3. Include affected versions and any proof-of-concept if available.

## Response timeline
We aim to acknowledge reports within 72 hours and provide remediation guidance as soon as feasible.
"""


def render_support_md() -> str:
    return """# Support

## Getting help
- Use GitHub Discussions for Q&A and design topics.
- Use Issues for bug reports and actionable work items.

## What to include
- What you expected vs what happened
- Steps to reproduce
- Versions (OS, runtime, dependencies)
- Logs or screenshots when applicable
"""


def render_usage_md(repo: str) -> str:
    return f"""# Usage

This document describes how to use **{repo}**.

## Quick start
- Describe installation
- Describe configuration
- Provide a minimal example

## Examples
- Add examples relevant to this repository

## Troubleshooting
- Common errors and how to resolve them
"""


def render_help_md(repo: str) -> str:
    return f"""# Help

This file provides operational help for **{repo}**.

## Common tasks
- Build / run
- Test
- Lint / format

## Where to ask questions
Use Discussions for Q&A and Issues for bugs/requests.
"""


def render_funding_yml(owner: str) -> str:
    return f"""github: [{owner}]
"""


def render_codeowners(owner: str) -> str:
    return f"""* @{owner}
"""


def render_issue_bug_form() -> str:
    return """name: Bug report
description: Report a reproducible bug
title: "[Bug]: "
labels: ["bug"]
body:
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: Describe the bug and what you expected.
      placeholder: Steps, expected vs actual...
    validations:
      required: true
  - type: textarea
    id: steps
    attributes:
      label: Steps to reproduce
      placeholder: 1) ... 2) ... 3) ...
    validations:
      required: true
  - type: input
    id: version
    attributes:
      label: Version / commit
      placeholder: e.g., v1.2.3 or commit SHA
  - type: textarea
    id: logs
    attributes:
      label: Relevant logs / output
      render: shell
"""


def render_issue_feature_form() -> str:
    return """name: Feature request
description: Propose a new feature or enhancement
title: "[Feature]: "
labels: ["enhancement"]
body:
  - type: textarea
    id: problem
    attributes:
      label: Problem statement
      description: What problem are you trying to solve?
    validations:
      required: true
  - type: textarea
    id: proposal
    attributes:
      label: Proposed solution
      description: Describe the solution you want.
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives considered
"""


def render_issue_template_config() -> str:
    return """blank_issues_enabled: true
contact_links:
  - name: Questions / Support
    url: https://github.com
    about: Use Discussions for Q&A where available.
"""


def render_pr_template_md() -> str:
    return """# Summary
Describe the change and why it is needed.

## Changes
- [ ] Feature
- [ ] Bug fix
- [ ] Refactor
- [ ] Documentation

## Checklist
- [ ] Tests added/updated (if applicable)
- [ ] Documentation updated (if applicable)
- [ ] Security considerations reviewed
"""


def render_discussion_template_ideas() -> str:
    return """title: "Idea"
body:
  - type: textarea
    id: idea
    attributes:
      label: Describe the idea
      description: Provide context, goals, and constraints.
    validations:
      required: true
  - type: textarea
    id: success
    attributes:
      label: Success criteria
"""


def render_release_yml() -> str:
    return """changelog:
  categories:
    - title: "Breaking Changes"
      labels:
        - "breaking-change"
    - title: "Features"
      labels:
        - "feature"
        - "enhancement"
    - title: "Bug Fixes"
      labels:
        - "bug"
    - title: "Dependency Updates"
      labels:
        - "dependencies"
    - title: "Other Changes"
      labels:
        - "*"
"""


def render_release_issue_form() -> str:
    return """name: Release request
description: Propose a new release
title: "[Release]: v"
labels: ["release"]
body:
  - type: input
    id: version
    attributes:
      label: Version
      placeholder: v1.2.3
    validations:
      required: true
  - type: textarea
    id: highlights
    attributes:
      label: Highlights
      description: What's new in this release?
    validations:
      required: true
  - type: textarea
    id: risks
    attributes:
      label: Risks / rollback plan
"""


def render_get_latest_release_workflow() -> str:
    return """name: Get Latest Release

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  latest-release:
    runs-on: ubuntu-latest
    steps:
      - name: Fetch latest release
        uses: actions/github-script@v7
        with:
          script: |
            const { owner, repo } = context.repo;
            try {
              const rel = await github.rest.repos.getLatestRelease({ owner, repo });
              core.summary.addHeading('Latest Release')
                .addRaw(`- Tag: ${rel.data.tag_name}\\n- Name: ${rel.data.name || ''}\\n- Published: ${rel.data.published_at}\\n`)
                .write();
            } catch (e) {
              core.summary.addHeading('Latest Release')
                .addRaw('No releases found or insufficient permissions.')
                .write();
            }
"""


def render_profile_readme(owner: str) -> str:
    return f"""# {owner}

This is my GitHub profile README.

## Focus areas
- Application Security (AppSec) automation
- CI/CD and supply chain security
- Developer tooling

## Repositories
Browse pinned repositories or search by topic/tag.
"""


def render_org_profile_readme(owner: str) -> str:
    return f"""# {owner}

Organization profile README.

## What we do
- Secure software delivery
- Automation and developer productivity
"""


# -----------------------------
# Bundles
# -----------------------------

def build_files_ghas(owner: str, repo: str, default_branch: str, ref: str, dependabot_interval: str, dependabot_open_pr_limit: int) -> List[FileToApply]:
    update_dirs = infer_dependabot_ecosystems(owner, repo, ref)
    langs = infer_codeql_languages(get_repo_languages(owner, repo))

    files: List[FileToApply] = []
    files.append(FileToApply(
        path=".github/dependabot.yml",
        content=render_dependabot_yml(update_dirs, dependabot_interval, dependabot_open_pr_limit),
        commit_message="chore: add Dependabot config",
    ))
    files.append(FileToApply(
        path=".github/workflows/dependency-review.yml",
        content=render_dependency_review_workflow_yml(),
        commit_message="chore: add dependency review workflow",
    ))
    files.append(FileToApply(
        path=".github/dependency-review-config.yml",
        content=render_dependency_review_config_yml(),
        commit_message="chore: add dependency review config",
    ))
    files.append(FileToApply(
        path=".github/workflows/codeql.yml",
        content=render_codeql_workflow_yml(default_branch, langs),
        commit_message="chore: add CodeQL workflow",
    ))
    files.append(FileToApply(
        path=".github/codeql/codeql-config.yml",
        content=render_codeql_config_yml(),
        commit_message="chore: add CodeQL config",
    ))
    files.append(FileToApply(
        path=".github/codeql/qlpack.yml",
        content=render_qlpack_yml(owner, repo),
        commit_message="chore: add CodeQL pack scaffold",
    ))
    return files


def build_files_community(owner: str, repo: str, cname: Optional[str]) -> List[FileToApply]:
    files: List[FileToApply] = []
    if cname:
        files.append(FileToApply("CNAME", cname.strip() + "\n", "chore: add CNAME for GitHub Pages"))

    files.append(FileToApply("CONTRIBUTING.md", render_contributing_md(owner, repo), "docs: add contributing guidelines"))
    files.append(FileToApply("CODE_OF_CONDUCT.md", render_code_of_conduct_md(), "docs: add code of conduct"))
    files.append(FileToApply("CITATION.cff", render_citation_cff(owner, repo), "docs: add citation metadata"))
    files.append(FileToApply("SECURITY.md", render_security_md(owner), "docs: add security policy"))
    files.append(FileToApply("SUPPORT.md", render_support_md(), "docs: add support guidelines"))
    files.append(FileToApply(".github/FUNDING.yml", render_funding_yml(owner), "chore: add funding configuration"))
    files.append(FileToApply(".github/CODEOWNERS", render_codeowners(owner), "chore: add CODEOWNERS"))
    files.append(FileToApply("docs/USAGE.md", render_usage_md(repo), "docs: add usage documentation"))
    files.append(FileToApply("docs/HELP.md", render_help_md(repo), "docs: add help documentation"))
    return files


def build_files_collaboration() -> List[FileToApply]:
    files: List[FileToApply] = []
    files.append(FileToApply(".github/ISSUE_TEMPLATE/bug_report.yml", render_issue_bug_form(), "docs: add bug report form"))
    files.append(FileToApply(".github/ISSUE_TEMPLATE/feature_request.yml", render_issue_feature_form(), "docs: add feature request form"))
    files.append(FileToApply(".github/ISSUE_TEMPLATE/config.yml", render_issue_template_config(), "docs: configure issue templates"))
    files.append(FileToApply(".github/PULL_REQUEST_TEMPLATE.md", render_pr_template_md(), "docs: add pull request template"))
    files.append(FileToApply(".github/DISCUSSION_TEMPLATE/idea.yml", render_discussion_template_ideas(), "docs: add discussion template"))
    return files


def build_files_release() -> List[FileToApply]:
    files: List[FileToApply] = []
    files.append(FileToApply(".github/release.yml", render_release_yml(), "chore: add release notes configuration"))
    files.append(FileToApply(".github/ISSUE_TEMPLATE/release.yml", render_release_issue_form(), "docs: add release request form"))
    files.append(FileToApply(".github/workflows/get-latest-release.yml", render_get_latest_release_workflow(), "chore: add latest release helper workflow"))
    return files


def build_files_readmes(owner: str, repo: str) -> List[FileToApply]:
    files: List[FileToApply] = []
    # Profile README: <owner>/<owner>
    if repo.lower() == owner.lower():
        files.append(FileToApply("README.md", render_profile_readme(owner), "docs: add profile README"))
    # Org profile README: <org>/.github repo uses profile/README.md
    if repo == ".github":
        files.append(FileToApply("profile/README.md", render_org_profile_readme(owner), "docs: add org profile README"))
    return files


def build_files_actions(owner: str, repo: str) -> List[FileToApply]:
    # Minimal stubs; apply org workflow starter templates only in .github repo
    files: List[FileToApply] = []
    files.append(FileToApply(
        ".github/actions/ci-summary/action.yml",
        """name: "CI Summary"
description: "Write a standard run summary"
runs:
  using: "composite"
  steps:
    - shell: bash
      run: |
        {
          echo "## CI Summary"
          echo ""
          echo "- Workflow: $GITHUB_WORKFLOW"
          echo "- Run: $GITHUB_RUN_ID"
          echo "- Ref: $GITHUB_REF"
        } >> "$GITHUB_STEP_SUMMARY"
""",
        "chore: add composite action scaffold",
    ))

    files.append(FileToApply(
        ".github/workflows/reusable-dependency-review.yml",
        """name: Reusable Dependency Review

on:
  workflow_call:

permissions:
  contents: read

jobs:
  dependency-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/dependency-review-action@v4
""",
        "chore: add reusable workflow scaffold",
    ))

    if repo == ".github":
        files.append(FileToApply(
            ".github/workflow-templates/config.yml",
            """blank_issues_enabled: true
contact_links: []
""",
            "chore: add workflow template config",
        ))
        files.append(FileToApply(
            ".github/workflow-templates/codeql.yml",
            """name: CodeQL (Starter)
on:
  workflow_dispatch:
jobs:
  noop:
    runs-on: ubuntu-latest
    steps:
      - run: echo "Starter template. Copy into .github/workflows in target repo."
""",
            "chore: add workflow starter template (CodeQL)",
        ))
    return files


# -----------------------------
# Apply logic (graceful existing file handling)
# -----------------------------

def ensure_file(
    owner: str,
    repo: str,
    branch: str,
    file: FileToApply,
    update_existing: bool,
    dry_run: bool,
) -> bool:
    ref = branch if not dry_run else get_default_branch(owner, repo, None)

    try:
        existing_sha = get_file_sha(owner, repo, file.path, ref=ref, use_tree_fallback=True)
    except RuntimeError as e:
        print(f"    ERROR: failed to check existing SHA for {file.path}: {e}")
        existing_sha = None

    if existing_sha and not update_existing:
        print(f"    SKIP: {file.path}")
        return False

    if existing_sha:
        print(f"    UPDATE: {file.path}")
        try:
            return put_file(
                owner,
                repo,
                file.path,
                file.content,
                file.commit_message,
                branch,
                existing_sha,
                update_if_exists=True,
                dry_run=dry_run,
            )
        except RuntimeError as e:
            print(f"    ERROR: failed to update {file.path}: {e}")
            return False

    print(f"    CREATE: {file.path}")
    try:
        return put_file(
            owner,
            repo,
            file.path,
            file.content,
            file.commit_message,
            branch,
            None,
            update_if_exists=update_existing,
            dry_run=dry_run,
        )
    except RuntimeError as e:
        print(f"    ERROR: failed to create {file.path}: {e}")
        return False


def normalize_include(items: Sequence[str]) -> Set[str]:
    """Normalize --include values.

    Supported groups:
      - ghas
      - community
      - collaboration
      - actions
      - release
      - readmes
      - all

    If no groups are provided, defaults to {"ghas"} to minimize surprise changes.
    """
    all_groups: Set[str] = {"ghas", "community", "collaboration", "actions", "release", "readmes"}
    if not items:
        return {"ghas"}

    mapping = {
        "ghas": "ghas",
        "advanced-security": "ghas",
        "advanced_security": "ghas",
        "security": "ghas",
        "community": "community",
        "community-health": "community",
        "community_health": "community",
        "health": "community",
        "collaboration": "collaboration",
        "collab": "collaboration",
        "templates": "collaboration",
        "actions": "actions",
        "workflows": "actions",
        "release": "release",
        "releases": "release",
        "readme": "readmes",
        "readmes": "readmes",
    }

    out: Set[str] = set()
    for raw in items:
        v = (raw or "").strip().lower()
        if not v:
            continue
        if v == "all":
            out |= all_groups
            continue
        out.add(mapping.get(v, v))

    known = out & all_groups
    return known if known else {"ghas"}

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Bulk add GitHub configuration files across many repos (Dependabot, CodeQL, templates, etc.)."
    )
    ap.add_argument("--owner", required=True, help="Org or user owner.")
    ap.add_argument("--mode", default="pr", choices=["pr"], help="Currently supported: pr")
    ap.add_argument("--dry-run", action="store_true")

    ap.add_argument(
        "--include",
        nargs="*",
        default=["ghas"],
        choices=["all", "community", "collaboration", "actions", "ghas", "release", "readmes"],
        help="What groups to include. Use 'all' for everything.",
    )

    ap.add_argument(
        "--repos",
        nargs="*",
        default=None,
        help="Optional list of repo names to limit execution to.",
    )

    ap.add_argument("--include-archived", action="store_true")
    ap.add_argument("--include-forks", action="store_true")

    ap.add_argument(
        "--branch",
        default=None,
        help="Head branch name to use (default: automation/github-configs/YYYYMMDD).",
    )
    ap.add_argument(
        "--update-existing",
        action="store_true",
        help="If set, update existing files when content differs. Otherwise leave existing files untouched.",
    )

    args = ap.parse_args()

    owner = args.owner
    include = normalize_include(args.include)

    target_branch = args.branch or build_branch_name()

    require_gh()

    repos = list_repos(owner, include_archived=args.include_archived, include_forks=args.include_forks)
    if args.repos:
        wanted = set(args.repos)
        repos = [r for r in repos if r.name in wanted]

    print(f"Target owner: {owner}")
    print(f"Repositories: {len(repos)}")
    print(f"Mode: {args.mode}  Dry-run: {args.dry_run}")
    print(f"Include: {', '.join(sorted(include))}")
    print(f"Branch: {target_branch}")
    print("")

    repo_failures: list[str] = []
    file_failures: list[str] = []

    for i, r in enumerate(repos, start=1):
        print(f"[{i}/{len(repos)}] {owner}/{r.name}")

        try:
            base_branch = r.default_branch
            # Ensure head branch exists (no-op in dry-run)
            create_branch(owner, r.name, target_branch, base_branch, dry_run=args.dry_run)

            files: list[FileSpec] = []
            if "community" in include:
                files.extend(build_files_community(owner, r.name, None))
            if "collaboration" in include:
                files.extend(build_files_collaboration())
            if "actions" in include:
                files.extend(build_files_actions(owner, r.name))
            if "ghas" in include:
                files.extend(build_files_ghas(owner, r.name, base_branch, base_branch, "weekly", 10))
            if "release" in include:
                files.extend(build_files_release())
            if "readmes" in include:
                files.extend(build_files_readmes(owner, r.name))

            changed_any = False

            for f in files:
                try:
                    changed = ensure_file(
                        owner,
                        r.name,
                        target_branch,
                        f,
                        update_existing=args.update_existing,
                        dry_run=args.dry_run,
                    )
                    changed_any = changed_any or changed
                except Exception as e:
                    msg = f"{owner}/{r.name}: {f.path}: {e}"
                    file_failures.append(msg)
                    print(f"    ERROR: {e}")
                    continue

            # PR creation (only if there were changes)
            if args.mode == "pr":
                try:
                    if changed_any:
                        # Build PR title and body based on what's included
                        included_items = sorted(include)
                        pr_title = "chore: Add GitHub repository configuration files"
                        
                        pr_body_parts = ["This PR adds the following GitHub configuration files:\n"]
                        if "ghas" in include:
                            pr_body_parts.append("- **GHAS**: Dependabot, CodeQL workflow/config, dependency review")
                        if "community" in include:
                            pr_body_parts.append("- **Community**: CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, SUPPORT, etc.")
                        if "collaboration" in include:
                            pr_body_parts.append("- **Collaboration**: Issue templates, PR template, discussion templates")
                        if "actions" in include:
                            pr_body_parts.append("- **Actions**: Reusable workflows and composite actions")
                        if "release" in include:
                            pr_body_parts.append("- **Release**: Release configuration and templates")
                        if "readmes" in include:
                            pr_body_parts.append("- **READMEs**: Profile and org READMEs")
                        
                        pr_body_parts.append("\nThese files help standardize repository configuration across the organization.")
                        pr_body = "\n".join(pr_body_parts)
                        
                        create_pull_request(owner, r.name, target_branch, base_branch, pr_title, pr_body, dry_run=args.dry_run)
                    else:
                        print("    NO-OP: no changes; skipping PR")
                except Exception as e:
                    msg = f"{owner}/{r.name}: PR: {e}"
                    file_failures.append(msg)
                    print(f"    ERROR: {e}")

        except Exception as e:
            repo_failures.append(f"{owner}/{r.name}: {e}")
            print(f"    ERROR: {e}")

        print("")

    print("Done.")
    if repo_failures or file_failures:
        if repo_failures:
            print("Repo failures:")
            for m in repo_failures:
                print(f"  - {m}")
        if file_failures:
            print("File/PR failures:")
            for m in file_failures:
                print(f"  - {m}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())