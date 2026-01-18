# GitHub Code Scanning Alert Manager (Python)

A production-oriented Python wrapper for the **GitHub REST API (Code Scanning)**, focused on **Code Scanning Alert Management** and designed to work seamlessly on a workstation where **GitHub CLI (`gh`) is installed and authenticated**.

This repository provides:

- A **generic REST client** (`GitHubRestClient`) with retries, backoff, pagination, and typed errors.
- A **domain client** (`CodeScanningClient`) implementing common alert operations:
  - List alerts (with filtering)
  - Get alert details
  - Update alert state (open/dismissed), including dismissal reason/comment
  - Assign/unassign alert assignees
  - List alert instances
  - Autofix operations (status, create, commit)

## Table of Contents

- [Why this exists](#why-this-exists)
- [Features](#features)
- [Repository layout](#repository-layout)
- [Requirements](#requirements)
- [Installation](#installation)
- [Authentication](#authentication)
  - [Option A: Environment variables](#option-a-environment-variables)
  - [Option B: GitHub CLI token fallback](#option-b-github-cli-token-fallback)
  - [Enterprise Server / GHES](#enterprise-server--ghes)
- [Quickstart](#quickstart)
- [Usage](#usage)
  - [Create clients](#create-clients)
  - [List alerts (filters)](#list-alerts-filters)
  - [Get alert details](#get-alert-details)
  - [Dismiss an alert (with audit comment)](#dismiss-an-alert-with-audit-comment)
  - [Re-open a dismissed alert](#re-open-a-dismissed-alert)
  - [Assign / unassign alerts](#assign--unassign-alerts)
  - [List instances of an alert](#list-instances-of-an-alert)
  - [Autofix workflow](#autofix-workflow)
- [Operational considerations](#operational-considerations)
  - [Permissions and scopes](#permissions-and-scopes)
  - [Rate limits, retries, and backoff](#rate-limits-retries-and-backoff)
  - [Pagination behavior](#pagination-behavior)
  - [Error handling](#error-handling)
  - [Logging and correlation](#logging-and-correlation)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
  - [Suggested enhancements / roadmap](#suggested-enhancements--roadmap)
- [Security notes](#security-notes)
- [License](#license)

---

## Why this exists

If you are running an AppSec or DevSecOps workflow, you often need consistent, automatable operations around Code Scanning alerts:

- Query alerts with stable filters (severity, tool, ref/PR, assignment state)
- Enforce triage policies (dismissals require audit context)
- Trigger/commit autofixes into controlled branches
- Build internal tooling that is **rate-limit aware** and emits actionable errors

This library emphasizes operational correctness and “automation-friendly” behavior.

---

## Features

### GitHubRestClient (low-level)
- Centralized headers:
  - `Accept: application/vnd.github+json`
  - `X-GitHub-Api-Version: 2022-11-28`
- Retry/backoff for transient failures (timeouts, connection errors, 5xx)
- Rate-limit detection (429 and 403 with rate-limit signals)
- Pagination via `Link` header `rel="next"`
- Typed exceptions that preserve:
  - HTTP status
  - response JSON (when available)
  - `X-GitHub-Request-Id` for correlation

### CodeScanningClient (domain-level)
- List alerts with filters: state, severity, tool_name/tool_guid, ref, PR, assignees, sort, direction
- Get alert details by number
- Update alert state:
  - `open` / `dismissed` (GitHub REST API only allows these via update endpoint)
  - Requires `dismissed_reason` when dismissing
- Dismiss convenience method with required audit comment
- List alert instances
- Autofix operations:
  - status check
  - create autofix
  - commit autofix to a pre-existing branch

---

## Repository layout

This repo is intentionally simple (single-file drop-in) to start:

```

.
├── code_scanning_api.py
└── README.md

```

Recommended evolution (when you want packaging + tests):

```

.
├── src/
│   └── gh_code_scanning/
│       ├── **init**.py
│       ├── rest.py
│       └── code_scanning.py
├── tests/
├── pyproject.toml
└── README.md

````

---

## Requirements

- Python **3.10+** (uses `X | Y` union types and `typing.Literal`)
- `requests`
- Optional but strongly recommended:
  - GitHub CLI (`gh`) installed and authenticated (`gh auth login`)

---

## Installation

### Minimal (local usage)

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install requests
````

Place `code_scanning_api.py` in your project, or keep it in this repo and import it.

### Recommended (requirements file)

If you add a `requirements.txt`:

```txt
requests>=2.31.0
```

Then install:

```bash
python -m pip install -r requirements.txt
```

---

## Authentication

This library uses the following token resolution order:

1. `GITHUB_TOKEN` environment variable
2. `GH_TOKEN` environment variable
3. `gh auth token` (GitHub CLI) as a fallback

### Option A: Environment variables

```bash
export GITHUB_TOKEN="YOUR_TOKEN"
# or:
export GH_TOKEN="YOUR_TOKEN"
```

### Option B: GitHub CLI token fallback

Authenticate GitHub CLI once:

```bash
gh auth login
```

Then the library can retrieve a token via:

```bash
gh auth token --hostname github.com
```

### Enterprise Server / GHES

If you are using GitHub Enterprise Server:

* Set the REST base URL to your GHES API endpoint (example):

  * `https://ghe.example.com/api/v3`
* Ensure `gh` is logged into your enterprise host:

  * `gh auth login --hostname ghe.example.com`

Then call `create_clients(base_url=..., hostname_for_gh=...)`.

---

## Quickstart

Run the module directly as a smoke test:

```bash
python code_scanning_api.py
```

Note: you must replace `OWNER` and `REPO` in the `__main__` block with a real repository.

---

## Usage

### Create clients

```python
from code_scanning_api import create_clients

rest, cs = create_clients()
```

To override base URL / API version / GH CLI hostname:

```python
rest, cs = create_clients(
    base_url="https://api.github.com",
    api_version="2022-11-28",
    hostname_for_gh="github.com",
)
```

---

### List alerts (filters)

```python
alerts = cs.list_alerts_for_repo(
    owner="my-org",
    repo="my-repo",
    state="open",
    severity="high",
    tool_name="CodeQL",
    sort="created",
    direction="desc",
    per_page=100,
)

print(f"alerts: {len(alerts)}")
```

Filter by assignees:

```python
# Alerts with at least one assignee
alerts = cs.list_alerts_for_repo("my-org", "my-repo", assignees="*")

# Alerts with no assignees
alerts = cs.list_alerts_for_repo("my-org", "my-repo", assignees="none")

# Alerts assigned to one or more users (comma-separated)
alerts = cs.list_alerts_for_repo("my-org", "my-repo", assignees="octocat,hubot")
```

List alerts for a specific branch/ref:

```python
alerts = cs.list_alerts_for_repo(
    "my-org",
    "my-repo",
    ref="refs/heads/main",
)
```

Or for a PR merge ref:

```python
alerts = cs.list_alerts_for_repo(
    "my-org",
    "my-repo",
    ref="refs/pull/123/merge",
)
```

---

### Get alert details

```python
alert = cs.get_alert("my-org", "my-repo", 123)
print(alert["state"], alert["rule"]["id"])
```

---

### Dismiss an alert (with audit comment)

Dismissal reasons must match GitHub’s expected strings:

* `"false positive"`
* `"won't fix"`
* `"used in tests"`

```python
result = cs.dismiss_alert(
    owner="my-org",
    repo="my-repo",
    alert_number=123,
    reason="false positive",
    comment="Triaged as non-exploitable; input is sanitized upstream. Ticket: SEC-1042.",
)
print(result["state"], result["dismissed_reason"])
```

Optional: request a dismissal review request (if your org uses it):

```python
result = cs.dismiss_alert(
    "my-org",
    "my-repo",
    123,
    reason="won't fix",
    comment="Accepted risk; compensating controls documented. Ticket: RISK-77.",
    create_request=True,
)
```

---

### Re-open a dismissed alert

```python
result = cs.reopen_alert("my-org", "my-repo", 123)
print(result["state"])  # open
```

---

### Assign / unassign alerts

Assign:

```python
result = cs.update_alert(
    "my-org",
    "my-repo",
    123,
    state="open",
    assignees=["octocat", "hubot"],
)
```

Unassign everyone:

```python
result = cs.update_alert(
    "my-org",
    "my-repo",
    123,
    state="open",
    assignees=[],
)
```

---

### List instances of an alert

```python
instances = cs.list_instances("my-org", "my-repo", 123, per_page=100)
for inst in instances:
    loc = inst.get("location", {})
    print(inst.get("ref"), loc.get("path"), loc.get("start_line"))
```

---

### Autofix workflow

#### 1) Check autofix status

```python
status = cs.get_autofix_status("my-org", "my-repo", 123)
print(status)
```

#### 2) Trigger autofix generation

```python
cs.create_autofix("my-org", "my-repo", 123)
```

#### 3) Commit autofix into an existing branch

> The branch **must already exist**.

```python
result = cs.commit_autofix(
    "my-org",
    "my-repo",
    123,
    target_ref="refs/heads/fix/codeql-autofix",
    message="Apply autofix for alert #123",
)
print(result)
```

---

## Operational considerations

### Permissions and scopes

Your token must have appropriate privileges for the endpoints you call.

Common patterns:

#### Classic PAT / OAuth app tokens

* Listing alerts typically requires `security_events` scope (or `public_repo` if only public repos).
* Committing autofixes requires `repo` scope (or `public_repo` if only public repos).

#### Fine-grained PATs / GitHub App tokens

Use least privilege per endpoint:

* List alerts: **Code scanning alerts (read)**
* Update alerts / Create autofix: **Code scanning alerts (write)**
* Commit autofix: **Contents (write)**

If you get 403 responses, verify:

* GitHub Advanced Security is enabled for the repository
* The repository is not archived
* Your token permissions match the endpoint

### Rate limits, retries, and backoff

`GitHubRestClient.request()` includes:

* Retries on connection/timeouts
* Retries on transient 5xx failures
* Rate-limit detection with optional short sleep if reset is imminent

You can tune retry behavior:

```python
rest = GitHubRestClient(
    token="...",
    max_retries=6,
    backoff_base_s=0.5,
    max_backoff_s=15.0,
)
```

### Pagination behavior

This library paginates using the GitHub `Link` response header and follows `rel="next"` until exhausted.

Important:

* Your `per_page` max is 100 (GitHub limit).
* Large repos may return many pages; design your automation to avoid frequent full scans.

### Error handling

This library raises typed exceptions:

* `GitHubAuthError` (401)
* `GitHubNotFoundError` (404)
* `GitHubRateLimitError` (429 or 403 with rate-limit signals)
* `GitHubApiError` (other 4xx/5xx errors)

Each exception includes the HTTP status and may include response JSON and request ID.

Example:

```python
from code_scanning_api import GitHubRateLimitError, GitHubApiError

try:
    alerts = cs.list_alerts_for_repo("my-org", "my-repo")
except GitHubRateLimitError as e:
    print("Rate limited; reset:", e.reset_epoch)
except GitHubApiError as e:
    print("API error:", e.status, e, "request_id:", e.request_id)
```

### Logging and correlation

GitHub responses often include `X-GitHub-Request-Id`. When troubleshooting, log that value so GitHub Support (or your internal platform team) can trace requests.

This client preserves that header in exceptions (`request_id`).

---

## Troubleshooting

### 401 Unauthorized

* Token missing or invalid
* Token does not have required scopes/permissions

Check:

* `echo $GITHUB_TOKEN`
* `gh auth status`

### 403 Forbidden

Common causes:

* Missing fine-grained permissions or missing PAT scopes
* GitHub Advanced Security not enabled for the repository
* Repository archived
* Rate limit exceeded

### 404 Not Found

Common causes:

* Wrong owner/repo
* Endpoint not available on your GitHub host/version (especially GHES)
* GitHub Advanced Security not enabled (some endpoints may mask as 404 depending on context)

### Quick endpoint validation with GitHub CLI

List alerts:

```bash
gh api \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "/repos/OWNER/REPO/code-scanning/alerts?state=open&per_page=100"
```

Dismiss an alert:

```bash
gh api --method PATCH \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "/repos/OWNER/REPO/code-scanning/alerts/ALERT_NUMBER" \
  -f state=dismissed \
  -f dismissed_reason="false positive" \
  -f dismissed_comment="Audit: validated false positive. Ticket: SEC-1042."
```

---

## Development

Suggested tooling (optional but recommended for a production-grade repo):

* Formatting: `black`
* Linting: `ruff`
* Type checking: `mypy`
* Tests: `pytest`

Example dev install:

```bash
python -m pip install black ruff mypy pytest
```

### Suggested enhancements / roadmap

If you want to grow this into a complete internal SDK/CLI for AppSec automation:

* Add structured JSON logging with consistent event IDs
* Add ETag support to reduce API calls on list/get operations
* Add deterministic incremental sync using cursor pagination (`before`/`after`)
* Add concurrency for bulk operations with rate-limit aware scheduling
* Add policy hooks:

  * Require ticket IDs in dismiss comments
  * Allowlist dismissals by rule ID / CWE tag
  * Auto-assign by CODEOWNERS mapping
* Add a CLI interface (argparse/typer) for common operations:

  * `list`, `dismiss`, `reopen`, `assign`, `instances`, `autofix`

---

## Security notes

* Treat tokens as secrets. Do not print or commit them.
* Prefer least privilege:

  * fine-grained PATs with minimal repo permissions
  * or GitHub Apps with scoped installation permissions
* If you log API errors, avoid dumping full response bodies unless necessary.

---

## License
