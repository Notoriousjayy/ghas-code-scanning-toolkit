# GitHub Code Scanning Alert Manager

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)
![Type Checked](https://img.shields.io/badge/type%20checked-mypy-blue)
![Security](https://img.shields.io/badge/security-bandit-yellow)
![GitHub API](https://img.shields.io/badge/GitHub%20API-2022--11--28-purple)

**Enterprise-grade Python toolkit for GitHub Advanced Security Code Scanning automation**

[Features](#features) •
[Installation](#installation) •
[Quick Start](#quick-start) •
[Documentation](#documentation) •
[Examples](#examples) •
[Contributing](#contributing)

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
  - [Why This Exists](#why-this-exists)
  - [Key Features](#key-features)
  - [Architecture](#architecture)
- [Getting Started](#getting-started)
  - [Requirements](#requirements)
  - [Installation](#installation)
    - [Standard Installation](#standard-installation)
    - [Docker Installation](#docker-installation)
    - [Development Installation](#development-installation)
  - [Quick Start](#quick-start)
- [Authentication](#authentication)
  - [Token Resolution](#token-resolution)
  - [Environment Variables](#environment-variables)
  - [GitHub CLI Integration](#github-cli-integration)
  - [GitHub Enterprise Server](#github-enterprise-server)
  - [Fine-Grained Permissions](#fine-grained-permissions)
- [Core Components](#core-components)
  - [GitHubRestClient](#githubrestclient)
  - [CodeScanningClient](#codescanningclient)
  - [Async Support](#async-support)
- [Usage Guide](#usage-guide)
  - [Client Initialization](#client-initialization)
  - [Alert Management](#alert-management)
  - [Alert Filtering](#alert-filtering)
  - [Alert Triage](#alert-triage)
  - [Alert Assignment](#alert-assignment)
  - [Alert Instances](#alert-instances)
  - [Autofix Workflows](#autofix-workflows)
- [Integration Patterns](#integration-patterns)
  - [ServiceNow Integration](#servicenow-integration)
  - [Webhook Integration](#webhook-integration)
  - [CI/CD Integration](#cicd-integration)
  - [SIEM Integration](#siem-integration)
- [API Reference](#api-reference)
  - [GitHubRestClient API](#githubrestclient-api)
  - [CodeScanningClient API](#codescanningclient-api)
  - [Exception Hierarchy](#exception-hierarchy)
- [Operational Considerations](#operational-considerations)
  - [Rate Limiting](#rate-limiting)
  - [Error Handling](#error-handling)
  - [Logging and Observability](#logging-and-observability)
  - [Performance Optimization](#performance-optimization)
- [Advanced Topics](#advanced-topics)
  - [Bulk Operations](#bulk-operations)
  - [Policy Enforcement](#policy-enforcement)
  - [Custom Workflows](#custom-workflows)
  - [Multi-Repository Operations](#multi-repository-operations)
- [Deployment](#deployment)
  - [Docker Deployment](#docker-deployment)
  - [Kubernetes Deployment](#kubernetes-deployment)
  - [AWS Lambda Deployment](#aws-lambda-deployment)
- [Examples](#examples)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
  - [Project Structure](#project-structure)
  - [Testing](#testing)
  - [Code Quality](#code-quality)
  - [Release Process](#release-process)
- [Contributing](#contributing)
- [Changelog](#changelog)
- [Security](#security)
- [License](#license)
- [Support](#support)

---

## Overview

### Why This Exists

Organizations running **GitHub Advanced Security (GHAS)** at scale need robust, production-ready automation for Code Scanning alert management. This toolkit addresses critical operational requirements:

**🎯 AppSec & DevSecOps Challenges**
- **Alert Triage at Scale**: Manage thousands of alerts across hundreds of repositories
- **Policy Enforcement**: Ensure dismissals include audit trails and approval workflows
- **SLA Compliance**: Track and remediate critical/high alerts within organizational SLAs
- **Integration Requirements**: Connect GHAS to existing security orchestration platforms (SOAR, SIEM, Ticketing)
- **Operational Visibility**: Centralize security metrics and reporting

**🔧 Technical Requirements**
- Rate-limit aware operations for API-intensive workflows
- Transient failure handling (retries, exponential backoff)
- Comprehensive error context for debugging and correlation
- Type-safe interfaces for IDE support and reduced runtime errors
- Extensible architecture for custom workflows

### Key Features

#### 🏗️ Production-Grade REST Client
- **Intelligent Retry Logic**: Exponential backoff for transient failures (connection errors, 5xx responses)
- **Rate Limit Management**: Automatic detection and handling of GitHub API rate limits
- **Comprehensive Pagination**: Follows `Link` header pagination to completion
- **Request Correlation**: Preserves `X-GitHub-Request-Id` for debugging and support escalation
- **Typed Exceptions**: Structured error handling with HTTP status, response body, and correlation IDs

#### 🔐 Code Scanning Operations
- **Alert Discovery**: Advanced filtering by state, severity, tool, ref, PR, assignees
- **Alert Triage**: Update state, dismiss with required audit trails, reopen dismissed alerts
- **Alert Assignment**: Assign/unassign security champions and development teams
- **Instance Analysis**: Retrieve detailed alert instances across branches and commits
- **Autofix Integration**: Trigger, monitor, and commit CodeQL autofixes

#### 🚀 Enterprise Integrations
- **ServiceNow**: Bidirectional sync with Security Incident Response (SIR) module
- **Webhooks**: Event-driven automation for alert lifecycle events
- **CI/CD**: GitHub Actions, GitLab CI, Jenkins integration patterns
- **SIEM**: Splunk, Azure Sentinel, Datadog integration examples

#### ⚡ Modern Python Features
- **Type Safety**: Full type hints for IDE autocomplete and static analysis
- **Async Support**: High-performance concurrent operations with `asyncio`
- **Python 3.10+**: Modern syntax (structural pattern matching, union types)
- **Logging**: Structured JSON logging for observability platforms

### Architecture

```mermaid
graph TB
    subgraph "Client Applications"
        CLI[CLI Tool]
        WEB[Web Dashboard]
        API[Internal API]
        LAMBDA[Lambda Functions]
    end
    
    subgraph "Code Scanning Toolkit"
        CS[CodeScanningClient]
        REST[GitHubRestClient]
        ASYNC[AsyncCodeScanningClient]
    end
    
    subgraph "GitHub Platform"
        GHAS[GitHub Advanced Security]
        ALERTS[Code Scanning Alerts API]
        AUTOFIX[Autofix API]
    end
    
    subgraph "Integration Layer"
        SN[ServiceNow]
        WEBHOOK[Webhook Handler]
        CICD[CI/CD Pipeline]
        SIEM[SIEM Platform]
    end
    
    CLI --> CS
    WEB --> CS
    API --> CS
    LAMBDA --> ASYNC
    
    CS --> REST
    ASYNC --> REST
    REST --> ALERTS
    REST --> AUTOFIX
    ALERTS --> GHAS
    AUTOFIX --> GHAS
    
    CS --> SN
    WEBHOOK --> CS
    CICD --> CS
    CS --> SIEM
    
    style CS fill:#4CAF50
    style REST fill:#2196F3
    style ASYNC fill:#FF9800
    style GHAS fill:#6610F2
```

#### Component Responsibilities

| Component | Responsibility | Key Features |
|-----------|---------------|--------------|
| `GitHubRestClient` | Low-level HTTP operations | Retry logic, rate limiting, pagination, correlation |
| `CodeScanningClient` | Code Scanning domain logic | Alert CRUD, filtering, triage, autofix orchestration |
| `AsyncCodeScanningClient` | High-performance operations | Concurrent API calls, batch processing |
| Integration Adapters | External system connectivity | ServiceNow, webhooks, SIEM, CI/CD |

---

## Getting Started

### Requirements

#### Core Requirements
- **Python**: 3.10 or later
- **Dependencies**: 
  - `requests >= 2.31.0` (sync client)
  - `aiohttp >= 3.9.0` (async client)
  - `pydantic >= 2.0.0` (data validation)

#### Optional but Recommended
- **GitHub CLI**: For automatic token resolution (`gh >= 2.40.0`)
- **Docker**: For containerized deployments (`docker >= 24.0.0`)
- **Git**: For development and contribution workflows

#### Development Requirements
- `black >= 23.0.0` (code formatting)
- `ruff >= 0.1.0` (linting)
- `mypy >= 1.7.0` (type checking)
- `pytest >= 7.4.0` (testing)
- `pytest-asyncio >= 0.21.0` (async testing)
- `pytest-cov >= 4.1.0` (coverage)

### Installation

#### Standard Installation

**Option 1: pip (PyPI)**
```bash
# Install latest stable release
pip install ghas-code-scanning-toolkit

# Install with async support
pip install ghas-code-scanning-toolkit[async]

# Install with all extras (async, dev tools, integrations)
pip install ghas-code-scanning-toolkit[all]
```

**Option 2: pip (from source)**
```bash
# Clone repository
git clone https://github.com/your-org/ghas-code-scanning-toolkit.git
cd ghas-code-scanning-toolkit

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install in editable mode
pip install -e .

# Or install with extras
pip install -e ".[async,dev]"
```

**Option 3: Poetry**
```bash
# Install with Poetry
poetry add ghas-code-scanning-toolkit

# Or add to pyproject.toml
[tool.poetry.dependencies]
ghas-code-scanning-toolkit = "^1.0.0"

# Then install
poetry install
```

**Option 4: Single-file drop-in**
```bash
# Download the standalone module
curl -O https://raw.githubusercontent.com/your-org/ghas-code-scanning-toolkit/main/code_scanning_api.py

# Install dependencies
pip install requests
```

#### Docker Installation

**Pull from Registry**
```bash
# Pull latest image
docker pull ghcr.io/your-org/ghas-toolkit:latest

# Pull specific version
docker pull ghcr.io/your-org/ghas-toolkit:1.0.0

# Run container
docker run --rm \
  -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
  ghcr.io/your-org/ghas-toolkit:latest \
  list-alerts --owner myorg --repo myrepo
```

**Build Locally**
```bash
# Build image
docker build -t ghas-toolkit:local .

# Run with environment variables
docker run --rm \
  -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
  -v $(pwd)/config:/app/config \
  ghas-toolkit:local
```

**Docker Compose**
```yaml
version: '3.8'

services:
  ghas-toolkit:
    image: ghcr.io/your-org/ghas-toolkit:latest
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - LOG_LEVEL=INFO
    volumes:
      - ./config:/app/config
      - ./output:/app/output
    command: ["list-alerts", "--owner", "myorg", "--repo", "myrepo"]
```

#### Development Installation

```bash
# Clone repository
git clone https://github.com/your-org/ghas-code-scanning-toolkit.git
cd ghas-code-scanning-toolkit

# Create development environment
python -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install -e ".[dev,test,docs]"

# Install pre-commit hooks
pre-commit install

# Run tests
pytest

# Run type checking
mypy src/

# Run linting
ruff check src/

# Format code
black src/ tests/
```

### Quick Start

#### Basic Usage

```python
from code_scanning_api import create_clients

# Initialize clients (auto-detects token from environment or gh CLI)
rest_client, cs_client = create_clients()

# List all open high-severity alerts
alerts = cs_client.list_alerts_for_repo(
    owner="my-org",
    repo="my-repo",
    state="open",
    severity="high"
)

print(f"Found {len(alerts)} high-severity alerts")

# Dismiss a false positive with audit trail
result = cs_client.dismiss_alert(
    owner="my-org",
    repo="my-repo",
    alert_number=42,
    reason="false positive",
    comment="Input validation added in commit abc123. Verified by security review. Ticket: SEC-1042"
)

print(f"Alert {result['number']} dismissed: {result['dismissed_reason']}")
```

#### CLI Quick Start

```bash
# Set authentication
export GITHUB_TOKEN="ghp_your_token_here"

# Or use GitHub CLI
gh auth login

# List open alerts
python -m ghas_toolkit list-alerts \
  --owner myorg \
  --repo myrepo \
  --state open \
  --severity high

# Dismiss an alert
python -m ghas_toolkit dismiss-alert \
  --owner myorg \
  --repo myrepo \
  --alert 42 \
  --reason "false positive" \
  --comment "Reviewed by security team. Ticket: SEC-1042"

# Generate alert report
python -m ghas_toolkit generate-report \
  --owner myorg \
  --repo myrepo \
  --output alerts-report.json
```

#### Async Quick Start

```python
import asyncio
from code_scanning_api import create_async_clients

async def main():
    # Initialize async clients
    rest_client, cs_client = await create_async_clients()
    
    # Process multiple repositories concurrently
    repos = ["repo1", "repo2", "repo3"]
    
    tasks = [
        cs_client.list_alerts_for_repo("my-org", repo, state="open")
        for repo in repos
    ]
    
    results = await asyncio.gather(*tasks)
    
    for repo, alerts in zip(repos, results):
        print(f"{repo}: {len(alerts)} open alerts")
    
    await rest_client.close()

asyncio.run(main())
```

---

## Authentication

### Token Resolution

The toolkit uses a hierarchical token resolution strategy:

```mermaid
graph LR
    A[Start] --> B{GITHUB_TOKEN set?}
    B -->|Yes| C[Use GITHUB_TOKEN]
    B -->|No| D{GH_TOKEN set?}
    D -->|Yes| E[Use GH_TOKEN]
    D -->|No| F{gh CLI available?}
    F -->|Yes| G[Run: gh auth token]
    F -->|No| H[Raise GitHubAuthError]
    
    C --> I[Validate Token]
    E --> I
    G --> I
    I --> J{Valid?}
    J -->|Yes| K[Initialize Client]
    J -->|No| H
    
    style C fill:#4CAF50
    style E fill:#4CAF50
    style G fill:#2196F3
    style H fill:#F44336
    style K fill:#4CAF50
```

### Environment Variables

**Standard Variables**
```bash
# Preferred: GITHUB_TOKEN
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Alternative: GH_TOKEN (used by GitHub CLI)
export GH_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**Advanced Configuration**
```bash
# GitHub Enterprise Server
export GITHUB_API_URL="https://github.example.com/api/v3"
export GITHUB_HOSTNAME="github.example.com"

# API Version (default: 2022-11-28)
export GITHUB_API_VERSION="2022-11-28"

# Rate Limiting
export GITHUB_MAX_RETRIES="5"
export GITHUB_BACKOFF_BASE="1.0"
export GITHUB_MAX_BACKOFF="30.0"

# Logging
export LOG_LEVEL="INFO"
export LOG_FORMAT="json"
```

**Docker Environment File**
```bash
# .env file
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
GITHUB_API_URL=https://api.github.com
LOG_LEVEL=INFO
```

### GitHub CLI Integration

The toolkit seamlessly integrates with GitHub CLI for token management:

**Initial Setup**
```bash
# Authenticate with GitHub
gh auth login

# Verify authentication
gh auth status

# Display token (for verification)
gh auth token
```

**Enterprise Server Setup**
```bash
# Authenticate with GHES
gh auth login --hostname github.example.com

# Verify GHES authentication
gh auth status --hostname github.example.com

# Get GHES token
gh auth token --hostname github.example.com
```

**Python Integration**
```python
from code_scanning_api import create_clients

# Automatically uses gh CLI token if environment variables not set
rest_client, cs_client = create_clients()

# Explicitly specify GHES hostname
rest_client, cs_client = create_clients(
    hostname_for_gh="github.example.com"
)
```

### GitHub Enterprise Server

**Configuration Example**
```python
from code_scanning_api import create_clients

# GHES configuration
rest_client, cs_client = create_clients(
    base_url="https://github.example.com/api/v3",
    api_version="2022-11-28",
    hostname_for_gh="github.example.com"
)

# List alerts on GHES instance
alerts = cs_client.list_alerts_for_repo(
    owner="enterprise-org",
    repo="enterprise-repo",
    state="open"
)
```

**Environment-based GHES Configuration**
```bash
# Set GHES environment variables
export GITHUB_API_URL="https://github.example.com/api/v3"
export GITHUB_HOSTNAME="github.example.com"
export GITHUB_TOKEN="ghp_your_ghes_token"

# Use with toolkit (auto-detects GHES configuration)
python -m ghas_toolkit list-alerts --owner myorg --repo myrepo
```

### Fine-Grained Permissions

GitHub fine-grained personal access tokens (PATs) and GitHub Apps require specific permissions:

#### Classic PAT Scopes
| Operation | Required Scope |
|-----------|----------------|
| List alerts (private repos) | `repo` or `security_events` |
| List alerts (public repos) | `public_repo` |
| Update alerts (dismiss/reopen) | `security_events` |
| Manage assignees | `security_events` |
| Commit autofixes | `repo` |

#### Fine-Grained PAT Permissions
| Operation | Required Permission | Access Level |
|-----------|---------------------|--------------|
| List alerts | Code scanning alerts | Read |
| Update alert state | Code scanning alerts | Write |
| Dismiss alerts | Code scanning alerts | Write |
| Manage assignees | Code scanning alerts | Write |
| List instances | Code scanning alerts | Read |
| Autofix status | Code scanning alerts | Read |
| Create autofix | Code scanning alerts | Write |
| Commit autofix | Contents | Write |

#### GitHub App Permissions
```yaml
permissions:
  contents: write
  security_events: write
  
# In GitHub App manifest
default_permissions:
  contents: write
  security_events: write
```

**Creating a Fine-Grained PAT**
```bash
# Navigate to: https://github.com/settings/tokens?type=beta

# Select required permissions:
# - Repository permissions:
#   - Code scanning alerts: Read and write
#   - Contents: Write (for autofixes)
#   - Metadata: Read (automatic)

# Set repository access:
# - All repositories (organization-wide)
# - Or specific repositories
```

**Validating Token Permissions**
```python
from code_scanning_api import validate_token_permissions

# Check token has required permissions
try:
    validate_token_permissions(
        token="ghp_xxx",
        owner="myorg",
        repo="myrepo",
        required_permissions=["security_events", "contents"]
    )
    print("Token has required permissions")
except PermissionError as e:
    print(f"Missing permissions: {e}")
```

---

## Core Components

### GitHubRestClient

Low-level HTTP client handling all GitHub REST API interactions.

**Key Features**
- Automatic retry with exponential backoff
- Rate limit detection and handling
- Link-header based pagination
- Request/response correlation
- Comprehensive error handling

**Basic Usage**
```python
from code_scanning_api import GitHubRestClient

# Initialize client
client = GitHubRestClient(
    token="ghp_xxx",
    base_url="https://api.github.com",
    api_version="2022-11-28",
    max_retries=5,
    backoff_base_s=1.0,
    max_backoff_s=30.0
)

# Make a request
response = client.request(
    method="GET",
    endpoint="/repos/myorg/myrepo/code-scanning/alerts",
    params={"state": "open", "per_page": 100}
)

# Paginated request
all_alerts = client.request_paginated(
    method="GET",
    endpoint="/repos/myorg/myrepo/code-scanning/alerts",
    params={"state": "open", "per_page": 100}
)
```

**Configuration Options**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `token` | `str` | Required | GitHub authentication token |
| `base_url` | `str` | `https://api.github.com` | GitHub API base URL |
| `api_version` | `str` | `2022-11-28` | GitHub API version header |
| `max_retries` | `int` | `5` | Maximum retry attempts |
| `backoff_base_s` | `float` | `1.0` | Base backoff delay (seconds) |
| `max_backoff_s` | `float` | `30.0` | Maximum backoff delay (seconds) |
| `timeout_s` | `float` | `30.0` | Request timeout (seconds) |

### CodeScanningClient

High-level client providing Code Scanning domain operations.

**Initialization**
```python
from code_scanning_api import CodeScanningClient, GitHubRestClient

# Option 1: Manual initialization
rest_client = GitHubRestClient(token="ghp_xxx")
cs_client = CodeScanningClient(rest_client)

# Option 2: Using helper function
from code_scanning_api import create_clients
rest_client, cs_client = create_clients()
```

**Core Methods**

| Method | Purpose | Returns |
|--------|---------|---------|
| `list_alerts_for_repo()` | List alerts with filtering | `List[Dict[str, Any]]` |
| `get_alert()` | Get alert details by number | `Dict[str, Any]` |
| `update_alert()` | Update alert state/assignees | `Dict[str, Any]` |
| `dismiss_alert()` | Dismiss alert with audit trail | `Dict[str, Any]` |
| `reopen_alert()` | Reopen dismissed alert | `Dict[str, Any]` |
| `list_instances()` | List alert instances | `List[Dict[str, Any]]` |
| `get_autofix_status()` | Get autofix status | `Dict[str, Any]` |
| `create_autofix()` | Trigger autofix generation | `Dict[str, Any]` |
| `commit_autofix()` | Commit autofix to branch | `Dict[str, Any]` |

### Async Support

High-performance asynchronous operations for bulk processing and concurrent workflows.

**Installation**
```bash
pip install ghas-code-scanning-toolkit[async]
```

**Basic Usage**
```python
import asyncio
from code_scanning_api import create_async_clients

async def process_alerts():
    # Initialize async clients
    rest_client, cs_client = await create_async_clients()
    
    try:
        # Fetch alerts asynchronously
        alerts = await cs_client.list_alerts_for_repo(
            owner="myorg",
            repo="myrepo",
            state="open"
        )
        
        print(f"Found {len(alerts)} alerts")
        
    finally:
        # Clean up connection pool
        await rest_client.close()

# Run async function
asyncio.run(process_alerts())
```

**Concurrent Multi-Repository Operations**
```python
import asyncio
from code_scanning_api import create_async_clients

async def scan_organization(org: str, repos: list[str]):
    rest_client, cs_client = await create_async_clients()
    
    try:
        # Create tasks for all repositories
        tasks = [
            cs_client.list_alerts_for_repo(org, repo, state="open")
            for repo in repos
        ]
        
        # Execute concurrently with rate limiting
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for repo, result in zip(repos, results):
            if isinstance(result, Exception):
                print(f"Error in {repo}: {result}")
            else:
                print(f"{repo}: {len(result)} open alerts")
                
    finally:
        await rest_client.close()

# Run with repository list
repos = ["repo1", "repo2", "repo3", "repo4", "repo5"]
asyncio.run(scan_organization("myorg", repos))
```

**Async Batch Operations**
```python
import asyncio
from code_scanning_api import create_async_clients

async def batch_dismiss_alerts(org: str, repo: str, alert_numbers: list[int]):
    """Dismiss multiple alerts concurrently with rate limiting."""
    rest_client, cs_client = await create_async_clients()
    
    try:
        # Create dismiss tasks
        tasks = [
            cs_client.dismiss_alert(
                owner=org,
                repo=repo,
                alert_number=num,
                reason="false positive",
                comment=f"Batch triage operation. Ticket: SEC-{num}"
            )
            for num in alert_numbers
        ]
        
        # Execute with concurrency limit (10 concurrent requests)
        semaphore = asyncio.Semaphore(10)
        
        async def limited_task(task):
            async with semaphore:
                return await task
        
        results = await asyncio.gather(
            *[limited_task(task) for task in tasks],
            return_exceptions=True
        )
        
        # Count successes and failures
        successes = sum(1 for r in results if not isinstance(r, Exception))
        failures = len(results) - successes
        
        print(f"Dismissed: {successes}, Failed: {failures}")
        
    finally:
        await rest_client.close()

# Run batch operation
alert_ids = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
asyncio.run(batch_dismiss_alerts("myorg", "myrepo", alert_ids))
```

**Async Context Manager**
```python
from code_scanning_api import AsyncCodeScanningContext

async def main():
    # Automatic client lifecycle management
    async with AsyncCodeScanningContext() as cs_client:
        alerts = await cs_client.list_alerts_for_repo(
            "myorg", "myrepo", state="open"
        )
        print(f"Found {len(alerts)} alerts")
    # Client automatically closed

asyncio.run(main())
```

**Performance Comparison**

| Operation | Sync (Sequential) | Async (Concurrent) | Speedup |
|-----------|-------------------|---------------------|---------|
| 10 repos, 100 alerts each | ~45s | ~6s | 7.5x |
| 50 repos, 50 alerts each | ~120s | ~12s | 10x |
| 100 alert dismissals | ~180s | ~18s | 10x |

---

## Usage Guide

### Client Initialization

**Simple Initialization**
```python
from code_scanning_api import create_clients

# Auto-detect authentication from environment or gh CLI
rest, cs = create_clients()
```

**Custom Configuration**
```python
from code_scanning_api import create_clients

rest, cs = create_clients(
    base_url="https://github.example.com/api/v3",  # GHES
    api_version="2022-11-28",
    hostname_for_gh="github.example.com",
    max_retries=10,
    backoff_base_s=2.0,
    max_backoff_s=60.0
)
```

**Manual Initialization with Custom Token**
```python
from code_scanning_api import GitHubRestClient, CodeScanningClient

# Initialize with specific token
rest = GitHubRestClient(token="ghp_custom_token_here")
cs = CodeScanningClient(rest)
```

### Alert Management

#### List Alerts

**Basic Listing**
```python
# List all open alerts
alerts = cs.list_alerts_for_repo(
    owner="myorg",
    repo="myrepo",
    state="open"
)

print(f"Found {len(alerts)} open alerts")
```

**Pagination Handling**
```python
# The client automatically handles pagination
# This will retrieve ALL alerts, not just the first page
all_alerts = cs.list_alerts_for_repo(
    owner="myorg",
    repo="myrepo",
    state="open",
    per_page=100  # Maximum: 100
)

print(f"Total alerts across all pages: {len(all_alerts)}")
```

#### Get Alert Details

```python
# Get detailed information for a specific alert
alert = cs.get_alert(
    owner="myorg",
    repo="myrepo",
    alert_number=42
)

# Access alert properties
print(f"Alert #{alert['number']}")
print(f"State: {alert['state']}")
print(f"Severity: {alert['rule']['severity']}")
print(f"Rule: {alert['rule']['id']}")
print(f"Tool: {alert['tool']['name']}")
print(f"Created: {alert['created_at']}")
print(f"URL: {alert['html_url']}")

# Check if dismissed
if alert['state'] == 'dismissed':
    print(f"Dismissed by: {alert['dismissed_by']['login']}")
    print(f"Reason: {alert['dismissed_reason']}")
    print(f"Comment: {alert['dismissed_comment']}")
```

### Alert Filtering

#### Filter by State

```python
# Open alerts only
open_alerts = cs.list_alerts_for_repo("myorg", "myrepo", state="open")

# Dismissed alerts only
dismissed = cs.list_alerts_for_repo("myorg", "myrepo", state="dismissed")

# Fixed alerts only
fixed = cs.list_alerts_for_repo("myorg", "myrepo", state="fixed")
```

#### Filter by Severity

```python
# Critical severity only
critical = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    state="open",
    severity="critical"
)

# High severity only
high = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    state="open",
    severity="high"
)

# Medium and low severity
medium = cs.list_alerts_for_repo("myorg", "myrepo", severity="medium")
low = cs.list_alerts_for_repo("myorg", "myrepo", severity="low")
```

#### Filter by Tool

```python
# CodeQL alerts only
codeql_alerts = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    state="open",
    tool_name="CodeQL"
)

# Filter by tool GUID (more specific)
specific_tool = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    tool_guid="4e79a32b-1234-5678-90ab-cdef12345678"
)
```

#### Filter by Branch/Ref

```python
# Main branch only
main_alerts = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    ref="refs/heads/main"
)

# Development branch
dev_alerts = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    ref="refs/heads/develop"
)

# Specific feature branch
feature_alerts = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    ref="refs/heads/feature/new-api"
)
```

#### Filter by Pull Request

```python
# Alerts introduced in PR #123
pr_alerts = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    ref="refs/pull/123/merge",
    pr=123
)
```

#### Filter by Assignment

```python
# Alerts with any assignee
assigned = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    assignees="*"
)

# Unassigned alerts
unassigned = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    assignees="none"
)

# Alerts assigned to specific user
user_alerts = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    assignees="octocat"
)

# Alerts assigned to multiple users (OR logic)
team_alerts = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    assignees="alice,bob,charlie"
)
```

#### Sort and Direction

```python
# Sort by creation date (newest first)
recent = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    sort="created",
    direction="desc"
)

# Sort by update date (oldest first)
stale = cs.list_alerts_for_repo(
    "myorg", "myrepo",
    sort="updated",
    direction="asc"
)
```

#### Combined Filters

```python
# Complex query: Open high-severity CodeQL alerts on main branch
# that are unassigned, sorted by creation date
alerts = cs.list_alerts_for_repo(
    owner="myorg",
    repo="myrepo",
    state="open",
    severity="high",
    tool_name="CodeQL",
    ref="refs/heads/main",
    assignees="none",
    sort="created",
    direction="desc",
    per_page=100
)

print(f"Found {len(alerts)} unassigned high-severity alerts on main")
```

### Alert Triage

#### Dismiss Alert with Audit Trail

```python
# Dismiss as false positive with detailed comment
result = cs.dismiss_alert(
    owner="myorg",
    repo="myrepo",
    alert_number=42,
    reason="false positive",
    comment="Reviewed by security team. Input is validated upstream in "
            "middleware layer (commit: abc123). User input cannot reach "
            "vulnerable code path. Verified with dynamic testing. "
            "Ticket: SEC-1042, Reviewer: @security-team"
)

print(f"Alert {result['number']} dismissed")
print(f"Dismissed by: {result['dismissed_by']['login']}")
print(f"Dismissed at: {result['dismissed_at']}")
```

**Valid Dismissal Reasons**
```python
# false positive - The alert is not a genuine security issue
cs.dismiss_alert(..., reason="false positive", comment="...")

# won't fix - Accepted risk, compensating controls in place
cs.dismiss_alert(..., reason="won't fix", comment="...")

# used in tests - Alert is in test code only
cs.dismiss_alert(..., reason="used in tests", comment="...")
```

**Dismissal with Review Request** (if enabled in organization)
```python
result = cs.dismiss_alert(
    owner="myorg",
    repo="myrepo",
    alert_number=42,
    reason="won't fix",
    comment="Accepted residual risk. Documented in risk register. "
            "Compensating controls: WAF rules, input sanitization at edge. "
            "Risk acceptance: RISK-2024-077",
    create_request=True  # Request dismissal review from security team
)
```

#### Reopen Dismissed Alert

```python
# Reopen a previously dismissed alert
result = cs.reopen_alert(
    owner="myorg",
    repo="myrepo",
    alert_number=42
)

print(f"Alert {result['number']} reopened")
print(f"State: {result['state']}")  # 'open'
```

#### Bulk Triage

```python
# Dismiss multiple alerts with the same reasoning
alert_numbers = [10, 11, 12, 13, 14]

for num in alert_numbers:
    try:
        result = cs.dismiss_alert(
            owner="myorg",
            repo="myrepo",
            alert_number=num,
            reason="used in tests",
            comment="All alerts in test suite. Test data sanitized. "
                    "Not reachable in production. Batch triage: TEST-2024-Q1"
        )
        print(f"✓ Alert {num} dismissed")
    except Exception as e:
        print(f"✗ Alert {num} failed: {e}")
```

### Alert Assignment

#### Assign Alerts

```python
# Assign to a single user
result = cs.update_alert(
    owner="myorg",
    repo="myrepo",
    alert_number=42,
    state="open",
    assignees=["security-champion"]
)

# Assign to multiple users
result = cs.update_alert(
    owner="myorg",
    repo="myrepo",
    alert_number=42,
    state="open",
    assignees=["alice", "bob", "security-team"]
)

print(f"Assigned to: {', '.join([u['login'] for u in result['assignees']])}")
```

#### Unassign Alerts

```python
# Remove all assignees
result = cs.update_alert(
    owner="myorg",
    repo="myrepo",
    alert_number=42,
    state="open",
    assignees=[]  # Empty list removes all assignees
)

print(f"Alert unassigned. Assignees: {result['assignees']}")  # []
```

#### Auto-Assignment by Rule

```python
# Map CWE categories to team members
CWE_OWNERS = {
    "CWE-79": ["xss-team", "frontend-security"],  # XSS
    "CWE-89": ["database-team", "backend-security"],  # SQL Injection
    "CWE-78": ["os-team", "platform-security"],  # OS Command Injection
}

# Get alert and determine assignees
alert = cs.get_alert("myorg", "myrepo", 42)
cwe_tags = alert['rule'].get('tags', [])

assignees = []
for tag in cwe_tags:
    if tag in CWE_OWNERS:
        assignees.extend(CWE_OWNERS[tag])

if assignees:
    cs.update_alert(
        "myorg", "myrepo", 42,
        state="open",
        assignees=list(set(assignees))  # Deduplicate
    )
    print(f"Auto-assigned to: {assignees}")
```

### Alert Instances

Alert instances show where the same issue appears across branches and commits.

```python
# List all instances of an alert
instances = cs.list_instances(
    owner="myorg",
    repo="myrepo",
    alert_number=42,
    per_page=100
)

print(f"Alert appears in {len(instances)} locations")

# Analyze instance details
for idx, inst in enumerate(instances, 1):
    loc = inst.get('location', {})
    print(f"\nInstance {idx}:")
    print(f"  Ref: {inst.get('ref')}")
    print(f"  Commit: {inst.get('commit_sha')[:7]}")
    print(f"  State: {inst.get('state')}")
    print(f"  File: {loc.get('path')}")
    print(f"  Line: {loc.get('start_line')}")
    print(f"  Message: {inst.get('message', {}).get('text', '')[:80]}")
```

**Instance Filtering**
```python
# Get instances for specific branch
main_instances = [
    inst for inst in instances
    if inst.get('ref') == 'refs/heads/main'
]

# Get instances still present (not fixed)
open_instances = [
    inst for inst in instances
    if inst.get('state') == 'open'
]

# Group instances by file
from collections import defaultdict

instances_by_file = defaultdict(list)
for inst in instances:
    path = inst.get('location', {}).get('path')
    if path:
        instances_by_file[path].append(inst)

for file, file_instances in instances_by_file.items():
    print(f"{file}: {len(file_instances)} instances")
```

### Autofix Workflows

CodeQL autofix allows automated remediation of certain vulnerability classes.

#### Check Autofix Status

```python
# Check if autofix is available for an alert
status = cs.get_autofix_status(
    owner="myorg",
    repo="myrepo",
    alert_number=42
)

print(f"Autofix status: {status}")
# Possible values: "not_available", "pending", "available", "failed"
```

#### Create Autofix

```python
# Trigger autofix generation
try:
    result = cs.create_autofix(
        owner="myorg",
        repo="myrepo",
        alert_number=42
    )
    print(f"Autofix created: {result}")
except GitHubApiError as e:
    if e.status == 422:
        print("Autofix not available for this alert type")
    else:
        raise
```

#### Monitor Autofix Progress

```python
import time

# Poll autofix status until complete
alert_number = 42
max_wait = 300  # 5 minutes
start_time = time.time()

while time.time() - start_time < max_wait:
    status = cs.get_autofix_status("myorg", "myrepo", alert_number)
    
    if status == "available":
        print("Autofix ready to commit")
        break
    elif status == "failed":
        print("Autofix generation failed")
        break
    elif status == "pending":
        print("Autofix generation in progress...")
        time.sleep(10)
    else:
        print(f"Autofix not available (status: {status})")
        break
else:
    print("Autofix timeout")
```

#### Commit Autofix

```python
# Commit autofix to existing branch
# Note: The branch MUST already exist

# Step 1: Create branch (using GitHub API or git)
# ... (branch creation not shown)

# Step 2: Commit autofix
result = cs.commit_autofix(
    owner="myorg",
    repo="myrepo",
    alert_number=42,
    target_ref="refs/heads/autofix/codeql-alert-42",
    message="🔒 Apply CodeQL autofix for alert #42\n\n"
            "Automatically generated fix for SQL injection vulnerability.\n"
            "Alert: https://github.com/myorg/myrepo/security/code-scanning/42\n"
            "Reviewed by: @security-team"
)

print(f"Autofix committed: {result}")
```

#### Complete Autofix Workflow

```python
import time
from typing import Optional

def apply_autofix_if_available(
    cs_client,
    owner: str,
    repo: str,
    alert_number: int,
    target_branch: str,
    timeout: int = 300
) -> Optional[dict]:
    """Complete autofix workflow with error handling."""
    
    # Step 1: Check initial status
    status = cs_client.get_autofix_status(owner, repo, alert_number)
    
    if status == "not_available":
        print(f"Alert {alert_number}: Autofix not supported for this alert type")
        return None
    
    # Step 2: Create autofix if needed
    if status != "available":
        print(f"Alert {alert_number}: Triggering autofix generation")
        cs_client.create_autofix(owner, repo, alert_number)
    
    # Step 3: Wait for autofix to be ready
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = cs_client.get_autofix_status(owner, repo, alert_number)
        
        if status == "available":
            print(f"Alert {alert_number}: Autofix ready")
            break
        elif status == "failed":
            print(f"Alert {alert_number}: Autofix generation failed")
            return None
        
        print(f"Alert {alert_number}: Waiting for autofix (status: {status})")
        time.sleep(10)
    else:
        print(f"Alert {alert_number}: Autofix timeout after {timeout}s")
        return None
    
    # Step 4: Commit autofix
    print(f"Alert {alert_number}: Committing autofix to {target_branch}")
    result = cs_client.commit_autofix(
        owner=owner,
        repo=repo,
        alert_number=alert_number,
        target_ref=f"refs/heads/{target_branch}",
        message=f"Apply autofix for CodeQL alert #{alert_number}"
    )
    
    print(f"Alert {alert_number}: Autofix committed successfully")
    return result

# Usage
from code_scanning_api import create_clients

rest, cs = create_clients()

result = apply_autofix_if_available(
    cs_client=cs,
    owner="myorg",
    repo="myrepo",
    alert_number=42,
    target_branch="autofix/alert-42",
    timeout=300
)
```

---

## Integration Patterns

### ServiceNow Integration

Bidirectional synchronization between GitHub Code Scanning alerts and ServiceNow Security Incident Response (SIR) module.

**Architecture**

```mermaid
sequenceDiagram
    participant GH as GitHub GHAS
    participant WH as Webhook Handler
    participant GHAS as GHAS Toolkit
    participant SN as ServiceNow SIR
    
    GH->>WH: code_scanning_alert (opened/dismissed)
    WH->>GHAS: Process alert event
    GHAS->>GHAS: Enrich alert data
    GHAS->>SN: Create/Update Security Incident
    SN-->>GHAS: Incident created (INC0012345)
    GHAS->>GH: Add comment with incident link
    
    Note over SN: Security team triages
    
    SN->>GHAS: Webhook: Incident resolved
    GHAS->>GH: Dismiss alert with audit comment
    GH-->>GHAS: Alert dismissed
    GHAS->>SN: Update incident state
```

**Implementation**

```python
from code_scanning_api import create_clients
from servicenow import ServiceNowClient
from typing import Dict, Any

class ServiceNowIntegration:
    """ServiceNow Security Incident Response integration."""
    
    def __init__(self, ghas_client, snow_client):
        self.ghas = ghas_client
        self.snow = snow_client
    
    def create_incident_from_alert(
        self,
        owner: str,
        repo: str,
        alert: Dict[str, Any]
    ) -> str:
        """Create ServiceNow incident from GHAS alert."""
        
        # Map GHAS severity to ServiceNow impact/urgency
        severity_mapping = {
            "critical": {"impact": "1", "urgency": "1"},
            "high": {"impact": "1", "urgency": "2"},
            "medium": {"impact": "2", "urgency": "2"},
            "low": {"impact": "3", "urgency": "3"}
        }
        
        severity = alert['rule'].get('severity', 'medium')
        snow_severity = severity_mapping.get(severity, {"impact": "3", "urgency": "3"})
        
        # Create incident
        incident_data = {
            "short_description": f"[GHAS] {alert['rule']['description']}",
            "description": self._format_incident_description(alert, owner, repo),
            "category": "Security",
            "subcategory": "Application Security",
            "impact": snow_severity["impact"],
            "urgency": snow_severity["urgency"],
            "assignment_group": "Application Security Team",
            "u_ghas_alert_number": alert['number'],
            "u_ghas_repository": f"{owner}/{repo}",
            "u_ghas_alert_url": alert['html_url'],
            "u_cwe_tags": ",".join(alert['rule'].get('tags', [])),
            "u_tool_name": alert['tool']['name']
        }
        
        incident = self.snow.create_incident(incident_data)
        incident_number = incident['number']
        
        # Add comment to GHAS alert with incident link
        self._add_incident_link_to_alert(owner, repo, alert['number'], incident_number)
        
        return incident_number
    
    def _format_incident_description(
        self,
        alert: Dict[str, Any],
        owner: str,
        repo: str
    ) -> str:
        """Format incident description with alert details."""
        
        rule = alert['rule']
        location = alert.get('most_recent_instance', {}).get('location', {})
        
        description = f"""
GitHub Advanced Security Code Scanning Alert

Repository: {owner}/{repo}
Alert Number: {alert['number']}
Alert URL: {alert['html_url']}

Vulnerability Details:
- Rule ID: {rule['id']}
- Description: {rule['description']}
- Severity: {rule.get('severity', 'N/A').upper()}
- CWE Tags: {', '.join(rule.get('tags', []))}

Location:
- File: {location.get('path', 'N/A')}
- Line: {location.get('start_line', 'N/A')}

Tool: {alert['tool']['name']} {alert['tool'].get('version', '')}

Created: {alert['created_at']}
Updated: {alert['updated_at']}

Remediation:
{rule.get('help', 'See alert URL for remediation guidance.')}
        """.strip()
        
        return description
    
    def _add_incident_link_to_alert(
        self,
        owner: str,
        repo: str,
        alert_number: int,
        incident_number: str
    ):
        """Add ServiceNow incident link to GHAS alert."""
        
        # Use GitHub API to add comment (requires separate implementation)
        # This is a simplified example
        snow_url = f"https://your-instance.service-now.com/nav_to.do?uri=incident.do?sysparm_query=number={incident_number}"
        
        comment = f"ServiceNow Incident Created: [{incident_number}]({snow_url})"
        
        # Add as alert comment or use update_alert
        # Implementation depends on your requirements
        pass
    
    def dismiss_alert_from_incident(
        self,
        owner: str,
        repo: str,
        alert_number: int,
        incident: Dict[str, Any]
    ):
        """Dismiss GHAS alert based on ServiceNow incident resolution."""
        
        # Map ServiceNow close codes to GHAS dismissal reasons
        close_code_mapping = {
            "False Positive": "false positive",
            "Resolved": "won't fix",  # If no code change needed
            "Test Environment": "used in tests"
        }
        
        close_code = incident.get('close_code', '')
        close_notes = incident.get('close_notes', '')
        
        dismissal_reason = close_code_mapping.get(
            close_code,
            "won't fix"  # Default
        )
        
        # Dismiss alert with incident context
        comment = f"""
Dismissed based on ServiceNow incident {incident['number']} resolution.

Close Code: {close_code}
Resolved By: {incident.get('resolved_by', 'N/A')}
Resolution Notes: {close_notes}

Incident URL: https://your-instance.service-now.com/nav_to.do?uri=incident.do?sysparm_query=number={incident['number']}
        """.strip()
        
        self.ghas.dismiss_alert(
            owner=owner,
            repo=repo,
            alert_number=alert_number,
            reason=dismissal_reason,
            comment=comment
        )

# Usage Example
from code_scanning_api import create_clients
from servicenow import ServiceNowClient

# Initialize clients
rest, ghas = create_clients()
snow = ServiceNowClient(
    instance="your-instance",
    username="integration_user",
    password="password"
)

integration = ServiceNowIntegration(ghas, snow)

# Create incident from alert
alert = ghas.get_alert("myorg", "myrepo", 42)
incident_number = integration.create_incident_from_alert("myorg", "myrepo", alert)
print(f"Created incident: {incident_number}")
```

**ServiceNow Webhook Handler**

```python
from flask import Flask, request, jsonify
from code_scanning_api import create_clients

app = Flask(__name__)
rest, ghas = create_clients()
snow = ServiceNowClient(...)  # Initialize
integration = ServiceNowIntegration(ghas, snow)

@app.route('/servicenow/webhook', methods=['POST'])
def servicenow_webhook():
    """Handle ServiceNow incident webhooks."""
    
    event = request.json
    
    # Check if incident is related to GHAS
    ghas_alert_number = event.get('u_ghas_alert_number')
    ghas_repo = event.get('u_ghas_repository')
    
    if not ghas_alert_number or not ghas_repo:
        return jsonify({"status": "ignored", "reason": "not a GHAS incident"}), 200
    
    owner, repo = ghas_repo.split('/')
    
    # Handle incident state changes
    if event['state'] == '6':  # Resolved
        integration.dismiss_alert_from_incident(
            owner=owner,
            repo=repo,
            alert_number=int(ghas_alert_number),
            incident=event
        )
        return jsonify({"status": "alert_dismissed"}), 200
    
    elif event['state'] == '7':  # Closed
        # Additional logging or metrics
        return jsonify({"status": "acknowledged"}), 200
    
    return jsonify({"status": "processed"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

### Webhook Integration

GitHub webhook handler for real-time alert event processing.

**Webhook Event Types**
- `code_scanning_alert.created`
- `code_scanning_alert.reopened`
- `code_scanning_alert.closed_by_user`
- `code_scanning_alert.fixed`
- `code_scanning_alert.appeared_in_branch`
- `code_scanning_alert.reopened_by_user`

**Flask Webhook Handler**

```python
from flask import Flask, request, jsonify
import hmac
import hashlib
from code_scanning_api import create_clients

app = Flask(__name__)
rest, ghas = create_clients()

WEBHOOK_SECRET = "your-webhook-secret"

def verify_signature(payload_body, signature_header):
    """Verify GitHub webhook signature."""
    if not signature_header:
        return False
    
    hash_object = hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    
    return hmac.compare_digest(expected_signature, signature_header)

@app.route('/github/webhook', methods=['POST'])
def github_webhook():
    """Handle GitHub Code Scanning webhooks."""
    
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, signature):
        return jsonify({"error": "Invalid signature"}), 403
    
    # Get event type
    event_type = request.headers.get('X-GitHub-Event')
    
    if event_type == 'code_scanning_alert':
        return handle_code_scanning_alert(request.json)
    
    return jsonify({"status": "ignored"}), 200

def handle_code_scanning_alert(payload):
    """Process code scanning alert webhook."""
    
    action = payload['action']
    alert = payload['alert']
    repository = payload['repository']
    
    owner = repository['owner']['login']
    repo = repository['name']
    alert_number = alert['number']
    
    print(f"Alert {alert_number} in {owner}/{repo}: {action}")
    
    # Auto-assign critical alerts
    if action == 'created' and alert['rule']['severity'] == 'critical':
        ghas.update_alert(
            owner=owner,
            repo=repo,
            alert_number=alert_number,
            state='open',
            assignees=['security-team', 'oncall-engineer']
        )
        return jsonify({"status": "assigned"}), 200
    
    # Trigger autofix for eligible alerts
    if action == 'created' and is_autofix_eligible(alert):
        try:
            ghas.create_autofix(owner, repo, alert_number)
            return jsonify({"status": "autofix_triggered"}), 200
        except Exception as e:
            print(f"Autofix failed: {e}")
    
    return jsonify({"status": "processed"}), 200

def is_autofix_eligible(alert):
    """Determine if alert is eligible for autofix."""
    # Example criteria
    eligible_rules = [
        'js/sql-injection',
        'py/sql-injection',
        'java/sql-injection'
    ]
    return alert['rule']['id'] in eligible_rules

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

### CI/CD Integration

#### GitHub Actions

**Workflow: Alert Triage**

```yaml
name: Code Scanning Alert Triage

on:
  code_scanning_alert:
    types: [created, reopened]

jobs:
  triage:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install ghas-code-scanning-toolkit
      
      - name: Auto-triage alert
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python - <<EOF
          from code_scanning_api import create_clients
          import json
          import os
          
          # Get event payload
          with open(os.environ['GITHUB_EVENT_PATH']) as f:
              event = json.load(f)
          
          alert = event['alert']
          repo_owner = event['repository']['owner']['login']
          repo_name = event['repository']['name']
          
          rest, ghas = create_clients()
          
          # Auto-assign based on severity
          if alert['rule']['severity'] == 'critical':
              ghas.update_alert(
                  owner=repo_owner,
                  repo=repo_name,
                  alert_number=alert['number'],
                  state='open',
                  assignees=['security-team']
              )
              print(f"Assigned critical alert {alert['number']} to security-team")
          
          EOF
```

**Workflow: Generate Alert Report**

```yaml
name: Weekly Security Report

on:
  schedule:
    - cron: '0 9 * * 1'  # Every Monday at 9 AM
  workflow_dispatch:

jobs:
  generate-report:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install ghas-code-scanning-toolkit pandas matplotlib
      
      - name: Generate report
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python scripts/generate_security_report.py \
            --owner ${{ github.repository_owner }} \
            --repo ${{ github.event.repository.name }} \
            --output report.html
      
      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: security-report
          path: report.html
      
      - name: Send to Slack
        uses: slackapi/slack-github-action@v1
        with:
          payload: |
            {
              "text": "Weekly Security Report Ready",
              "attachments": [{
                "color": "good",
                "text": "View report in workflow artifacts"
              }]
            }
        env:
          SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

#### GitLab CI

```yaml
# .gitlab-ci.yml

stages:
  - security
  - report

variables:
  GITHUB_TOKEN: $GITHUB_TOKEN

ghas_sync:
  stage: security
  image: python:3.11
  script:
    - pip install ghas-code-scanning-toolkit
    - python scripts/sync_alerts_to_gitlab.py
  only:
    - schedules

security_report:
  stage: report
  image: python:3.11
  script:
    - pip install ghas-code-scanning-toolkit pandas
    - python scripts/generate_report.py --output report.html
  artifacts:
    paths:
      - report.html
    expire_in: 30 days
  only:
    - schedules
```

#### Jenkins Pipeline

```groovy
pipeline {
    agent any
    
    environment {
        GITHUB_TOKEN = credentials('github-token')
    }
    
    stages {
        stage('Setup') {
            steps {
                sh 'pip install ghas-code-scanning-toolkit'
            }
        }
        
        stage('Sync Alerts') {
            steps {
                script {
                    sh '''
                        python - <<EOF
from code_scanning_api import create_clients

rest, ghas = create_clients()

# List all open high/critical alerts
alerts = ghas.list_alerts_for_repo(
    owner="myorg",
    repo="myrepo",
    state="open",
    severity="high"
)

print(f"Found {len(alerts)} high-severity alerts")

# Create JIRA tickets for untracked alerts
# (Implementation depends on your JIRA integration)
EOF
                    '''
                }
            }
        }
        
        stage('Generate Report') {
            steps {
                sh 'python scripts/generate_jenkins_report.py'
                publishHTML([
                    reportDir: 'reports',
                    reportFiles: 'security-report.html',
                    reportName: 'Security Report'
                ])
            }
        }
    }
    
    post {
        always {
            cleanWs()
        }
    }
}
```

### SIEM Integration

#### Splunk Integration

```python
import json
import requests
from code_scanning_api import create_clients
from datetime import datetime, timedelta

class SplunkIntegration:
    """Send GHAS alerts to Splunk HEC."""
    
    def __init__(self, hec_url: str, hec_token: str):
        self.hec_url = hec_url
        self.hec_token = hec_token
    
    def send_alert(self, owner: str, repo: str, alert: dict):
        """Send alert to Splunk."""
        
        event = {
            "time": datetime.now().timestamp(),
            "host": "github.com",
            "source": "ghas",
            "sourcetype": "code_scanning_alert",
            "event": {
                "repository": f"{owner}/{repo}",
                "alert_number": alert['number'],
                "alert_url": alert['html_url'],
                "state": alert['state'],
                "severity": alert['rule'].get('severity'),
                "rule_id": alert['rule']['id'],
                "rule_description": alert['rule']['description'],
                "tool_name": alert['tool']['name'],
                "cwe_tags": alert['rule'].get('tags', []),
                "created_at": alert['created_at'],
                "updated_at": alert['updated_at'],
                "dismissed_by": alert.get('dismissed_by', {}).get('login'),
                "dismissed_reason": alert.get('dismissed_reason'),
            }
        }
        
        headers = {
            "Authorization": f"Splunk {self.hec_token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{self.hec_url}/services/collector/event",
            headers=headers,
            json=event
        )
        
        response.raise_for_status()
        return response.json()

# Usage
rest, ghas = create_clients()
splunk = SplunkIntegration(
    hec_url="https://splunk.example.com:8088",
    hec_token="your-hec-token"
)

# Send all alerts from last 24 hours
cutoff = datetime.now() - timedelta(days=1)

alerts = ghas.list_alerts_for_repo("myorg", "myrepo", state="open")

for alert in alerts:
    alert_created = datetime.fromisoformat(alert['created_at'].replace('Z', '+00:00'))
    if alert_created > cutoff:
        splunk.send_alert("myorg", "myrepo", alert)
        print(f"Sent alert {alert['number']} to Splunk")
```

---

## API Reference

### GitHubRestClient API

#### Constructor

```python
GitHubRestClient(
    token: str,
    base_url: str = "https://api.github.com",
    api_version: str = "2022-11-28",
    max_retries: int = 5,
    backoff_base_s: float = 1.0,
    max_backoff_s: float = 30.0,
    timeout_s: float = 30.0
)
```

**Parameters:**
- `token`: GitHub authentication token (required)
- `base_url`: API base URL (default: `https://api.github.com`)
- `api_version`: API version header (default: `2022-11-28`)
- `max_retries`: Maximum retry attempts (default: `5`)
- `backoff_base_s`: Base backoff delay in seconds (default: `1.0`)
- `max_backoff_s`: Maximum backoff delay in seconds (default: `30.0`)
- `timeout_s`: Request timeout in seconds (default: `30.0`)

#### Methods

##### `request()`

```python
def request(
    method: str,
    endpoint: str,
    params: dict[str, Any] | None = None,
    json_data: dict[str, Any] | None = None
) -> dict[str, Any]
```

Execute a single HTTP request with retry logic.

**Parameters:**
- `method`: HTTP method (`GET`, `POST`, `PATCH`, `DELETE`)
- `endpoint`: API endpoint path (e.g., `/repos/owner/repo/code-scanning/alerts`)
- `params`: URL query parameters (optional)
- `json_data`: JSON request body (optional)

**Returns:** Response JSON as dictionary

**Raises:**
- `GitHubAuthError`: 401 Unauthorized
- `GitHubNotFoundError`: 404 Not Found
- `GitHubRateLimitError`: 429 Rate Limited
- `GitHubApiError`: Other API errors

##### `request_paginated()`

```python
def request_paginated(
    method: str,
    endpoint: str,
    params: dict[str, Any] | None = None
) -> list[dict[str, Any]]
```

Execute paginated request, following `Link` header until exhausted.

**Parameters:**
- `method`: HTTP method (`GET` only)
- `endpoint`: API endpoint path
- `params`: URL query parameters (optional)

**Returns:** List of all results across pages

**Raises:** Same as `request()`

### CodeScanningClient API

#### Constructor

```python
CodeScanningClient(rest_client: GitHubRestClient)
```

**Parameters:**
- `rest_client`: Initialized `GitHubRestClient` instance

#### Methods

##### `list_alerts_for_repo()`

```python
def list_alerts_for_repo(
    owner: str,
    repo: str,
    state: Literal["open", "dismissed", "fixed"] | None = None,
    severity: Literal["critical", "high", "medium", "low", "warning", "note", "error"] | None = None,
    tool_name: str | None = None,
    tool_guid: str | None = None,
    ref: str | None = None,
    pr: int | None = None,
    assignees: str | None = None,
    sort: Literal["created", "updated"] = "created",
    direction: Literal["asc", "desc"] = "desc",
    per_page: int = 100
) -> list[dict[str, Any]]
```

List Code Scanning alerts with optional filtering.

**Parameters:**
- `owner`: Repository owner
- `repo`: Repository name
- `state`: Filter by alert state (optional)
- `severity`: Filter by severity level (optional)
- `tool_name`: Filter by tool name (optional)
- `tool_guid`: Filter by tool GUID (optional)
- `ref`: Filter by Git ref (optional)
- `pr`: Filter by PR number (optional)
- `assignees`: Filter by assignees - `"*"` (any), `"none"`, or comma-separated usernames (optional)
- `sort`: Sort field (default: `created`)
- `direction`: Sort direction (default: `desc`)
- `per_page`: Results per page, max 100 (default: `100`)

**Returns:** List of alert dictionaries

##### `get_alert()`

```python
def get_alert(
    owner: str,
    repo: str,
    alert_number: int
) -> dict[str, Any]
```

Get detailed information for a specific alert.

**Parameters:**
- `owner`: Repository owner
- `repo`: Repository name
- `alert_number`: Alert number

**Returns:** Alert dictionary

##### `update_alert()`

```python
def update_alert(
    owner: str,
    repo: str,
    alert_number: int,
    state: Literal["open", "dismissed"],
    dismissed_reason: Literal["false positive", "won't fix", "used in tests"] | None = None,
    dismissed_comment: str | None = None,
    assignees: list[str] | None = None
) -> dict[str, Any]
```

Update alert state and/or assignees.

**Parameters:**
- `owner`: Repository owner
- `repo`: Repository name
- `alert_number`: Alert number
- `state`: New state (`open` or `dismissed`)
- `dismissed_reason`: Required when `state="dismissed"`
- `dismissed_comment`: Optional dismissal comment
- `assignees`: List of assignee usernames (optional)

**Returns:** Updated alert dictionary

##### `dismiss_alert()`

```python
def dismiss_alert(
    owner: str,
    repo: str,
    alert_number: int,
    reason: Literal["false positive", "won't fix", "used in tests"],
    comment: str,
    create_request: bool = False
) -> dict[str, Any]
```

Dismiss alert with required audit trail.

**Parameters:**
- `owner`: Repository owner
- `repo`: Repository name
- `alert_number`: Alert number
- `reason`: Dismissal reason
- `comment`: Dismissal comment (required for audit)
- `create_request`: Request dismissal review (optional, default: `False`)

**Returns:** Dismissed alert dictionary

##### `reopen_alert()`

```python
def reopen_alert(
    owner: str,
    repo: str,
    alert_number: int
) -> dict[str, Any]
```

Reopen a dismissed alert.

**Parameters:**
- `owner`: Repository owner
- `repo`: Repository name
- `alert_number`: Alert number

**Returns:** Reopened alert dictionary

##### `list_instances()`

```python
def list_instances(
    owner: str,
    repo: str,
    alert_number: int,
    ref: str | None = None,
    per_page: int = 100
) -> list[dict[str, Any]]
```

List instances of an alert across branches/commits.

**Parameters:**
- `owner`: Repository owner
- `repo`: Repository name
- `alert_number`: Alert number
- `ref`: Filter by Git ref (optional)
- `per_page`: Results per page, max 100 (default: `100`)

**Returns:** List of instance dictionaries

##### `get_autofix_status()`

```python
def get_autofix_status(
    owner: str,
    repo: str,
    alert_number: int
) -> str
```

Get autofix status for an alert.

**Parameters:**
- `owner`: Repository owner
- `repo`: Repository name
- `alert_number`: Alert number

**Returns:** Status string (`"not_available"`, `"pending"`, `"available"`, `"failed"`)

##### `create_autofix()`

```python
def create_autofix(
    owner: str,
    repo: str,
    alert_number: int
) -> dict[str, Any]
```

Trigger autofix generation.

**Parameters:**
- `owner`: Repository owner
- `repo`: Repository name
- `alert_number`: Alert number

**Returns:** Autofix creation response

##### `commit_autofix()`

```python
def commit_autofix(
    owner: str,
    repo: str,
    alert_number: int,
    target_ref: str,
    message: str
) -> dict[str, Any]
```

Commit autofix to existing branch.

**Parameters:**
- `owner`: Repository owner
- `repo`: Repository name
- `alert_number`: Alert number
- `target_ref`: Target branch ref (must exist, e.g., `refs/heads/fix-branch`)
- `message`: Commit message

**Returns:** Commit response

### Exception Hierarchy

```python
GitHubApiError
├── GitHubAuthError          # 401 Unauthorized
├── GitHubNotFoundError      # 404 Not Found
└── GitHubRateLimitError     # 429 or 403 with rate limit headers
```

**Base Exception: `GitHubApiError`**

```python
class GitHubApiError(Exception):
    def __init__(
        self,
        message: str,
        status: int,
        response_json: dict | None = None,
        request_id: str | None = None
    ):
        self.message = message
        self.status = status
        self.response_json = response_json
        self.request_id = request_id
```

**Attributes:**
- `message`: Error description
- `status`: HTTP status code
- `response_json`: Response body (if JSON)
- `request_id`: `X-GitHub-Request-Id` for correlation

**Usage:**

```python
from code_scanning_api import GitHubApiError, GitHubRateLimitError

try:
    alerts = cs.list_alerts_for_repo("myorg", "myrepo")
except GitHubRateLimitError as e:
    print(f"Rate limited. Reset at: {e.reset_epoch}")
    print(f"Request ID: {e.request_id}")
except GitHubApiError as e:
    print(f"API error {e.status}: {e.message}")
    print(f"Request ID: {e.request_id}")
```

---

## Operational Considerations

### Rate Limiting

GitHub API rate limits vary by authentication type:

| Authentication Type | Rate Limit | Notes |
|---------------------|------------|-------|
| Unauthenticated | 60 requests/hour | Not recommended |
| OAuth / PAT | 5,000 requests/hour | Standard |
| GitHub App (user-to-server) | 5,000 requests/hour | Per installation |
| GitHub App (server-to-server) | 15,000 requests/hour | Per installation |

**Rate Limit Headers**

The toolkit monitors these response headers:
- `X-RateLimit-Limit`: Total requests allowed per hour
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

**Handling Rate Limits**

```python
from code_scanning_api import GitHubRateLimitError
import time

try:
    alerts = cs.list_alerts_for_repo("myorg", "myrepo")
except GitHubRateLimitError as e:
    # Calculate wait time
    reset_time = e.reset_epoch
    wait_seconds = reset_time - time.time()
    
    print(f"Rate limited. Waiting {wait_seconds:.0f} seconds...")
    time.sleep(wait_seconds + 1)  # Add buffer
    
    # Retry
    alerts = cs.list_alerts_for_repo("myorg", "myrepo")
```

**Proactive Rate Limit Management**

```python
def get_rate_limit_info(rest_client):
    """Check current rate limit status."""
    response = rest_client.request("GET", "/rate_limit")
    
    core = response['resources']['core']
    
    return {
        "limit": core['limit'],
        "remaining": core['remaining'],
        "reset": core['reset'],
        "percent_used": ((core['limit'] - core['remaining']) / core['limit']) * 100
    }

# Check before bulk operations
info = get_rate_limit_info(rest)
print(f"Rate limit: {info['remaining']}/{info['limit']} ({info['percent_used']:.1f}% used)")

if info['remaining'] < 100:
    print("Warning: Low rate limit remaining")
```

### Error Handling

**Comprehensive Error Handling Pattern**

```python
from code_scanning_api import (
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubApiError,
    create_clients
)
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def safe_alert_operation(owner, repo, alert_number, max_retries=3):
    """Execute alert operation with comprehensive error handling."""
    
    rest, cs = create_clients()
    
    for attempt in range(max_retries):
        try:
            alert = cs.get_alert(owner, repo, alert_number)
            return alert
            
        except GitHubAuthError as e:
            logger.error(f"Authentication failed: {e.message}")
            logger.error(f"Request ID: {e.request_id}")
            raise  # Don't retry auth errors
            
        except GitHubNotFoundError as e:
            logger.error(f"Resource not found: {e.message}")
            logger.error(f"Possible causes:")
            logger.error(f"  - Repository doesn't exist or is inaccessible")
            logger.error(f"  - Alert number {alert_number} doesn't exist")
            logger.error(f"  - GHAS not enabled for repository")
            logger.error(f"Request ID: {e.request_id}")
            raise  # Don't retry 404s
            
        except GitHubRateLimitError as e:
            if attempt < max_retries - 1:
                wait_time = e.reset_epoch - time.time() + 1
                logger.warning(f"Rate limited. Waiting {wait_time:.0f}s...")
                logger.info(f"Request ID: {e.request_id}")
                time.sleep(wait_time)
                continue
            else:
                logger.error("Rate limit retry exhausted")
                raise
                
        except GitHubApiError as e:
            logger.error(f"API error {e.status}: {e.message}")
            logger.error(f"Request ID: {e.request_id}")
            
            if e.response_json:
                logger.error(f"Response: {e.response_json}")
            
            if 500 <= e.status < 600 and attempt < max_retries - 1:
                # Retry server errors
                backoff = 2 ** attempt
                logger.info(f"Retrying in {backoff}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(backoff)
                continue
            else:
                raise
    
    raise RuntimeError("Max retries exceeded")

# Usage
try:
    alert = safe_alert_operation("myorg", "myrepo", 42)
    print(f"Retrieved alert: {alert['number']}")
except Exception as e:
    logger.error(f"Operation failed: {e}")
```

### Logging and Observability

**Structured JSON Logging**

```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""
    
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add custom fields
        if hasattr(record, 'request_id'):
            log_data["request_id"] = record.request_id
        if hasattr(record, 'alert_number'):
            log_data["alert_number"] = record.alert_number
        if hasattr(record, 'repository'):
            log_data["repository"] = record.repository
        
        return json.dumps(log_data)

# Configure logging
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())

logger = logging.getLogger("ghas_toolkit")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Usage with extra fields
logger.info(
    "Alert dismissed",
    extra={
        "request_id": "abc123",
        "alert_number": 42,
        "repository": "myorg/myrepo"
    }
)
```

**Request Correlation**

```python
import uuid
from contextvars import ContextVar

# Context variable for request correlation
correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')

def generate_correlation_id():
    """Generate unique correlation ID."""
    return str(uuid.uuid4())

def process_with_correlation(owner, repo, alert_number):
    """Execute operation with correlation tracking."""
    
    # Set correlation ID for this operation
    cid = generate_correlation_id()
    correlation_id.set(cid)
    
    logger = logging.getLogger(__name__)
    logger.info(
        f"Starting alert operation",
        extra={
            "correlation_id": cid,
            "repository": f"{owner}/{repo}",
            "alert_number": alert_number
        }
    )
    
    try:
        rest, cs = create_clients()
        alert = cs.get_alert(owner, repo, alert_number)
        
        logger.info(
            "Alert retrieved successfully",
            extra={"correlation_id": cid}
        )
        
        return alert
        
    except GitHubApiError as e:
        logger.error(
            f"Alert operation failed",
            extra={
                "correlation_id": cid,
                "github_request_id": e.request_id,
                "status_code": e.status
            }
        )
        raise
```

### Performance Optimization

**Batch Operations with Connection Pooling**

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_optimized_rest_client():
    """Create REST client with connection pooling."""
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST", "PATCH"]
    )
    
    # Create adapter with connection pooling
    adapter = HTTPAdapter(
        max_retries=retry_strategy,
        pool_connections=20,
        pool_maxsize=20
    )
    
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    # Use session in GitHubRestClient
    # (requires modification to GitHubRestClient to accept session)
    
    return session
```

**Caching Alert Data**

```python
from functools import lru_cache
from datetime import datetime, timedelta

class CachedCodeScanningClient:
    """Code Scanning client with caching."""
    
    def __init__(self, cs_client):
        self.cs = cs_client
        self._cache = {}
        self._cache_ttl = timedelta(minutes=5)
    
    def get_alert_cached(self, owner, repo, alert_number):
        """Get alert with caching."""
        
        cache_key = f"{owner}/{repo}/{alert_number}"
        now = datetime.now()
        
        # Check cache
        if cache_key in self._cache:
            cached_alert, cached_time = self._cache[cache_key]
            if now - cached_time < self._cache_ttl:
                return cached_alert
        
        # Fetch from API
        alert = self.cs.get_alert(owner, repo, alert_number)
        
        # Update cache
        self._cache[cache_key] = (alert, now)
        
        return alert
    
    def invalidate_cache(self, owner=None, repo=None, alert_number=None):
        """Invalidate cache entries."""
        
        if alert_number:
            cache_key = f"{owner}/{repo}/{alert_number}"
            self._cache.pop(cache_key, None)
        elif repo:
            # Invalidate all alerts in repository
            prefix = f"{owner}/{repo}/"
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]
        else:
            # Clear entire cache
            self._cache.clear()
```

---

## Advanced Topics

### Bulk Operations

**Parallel Alert Processing**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from code_scanning_api import create_clients
import logging

logger = logging.getLogger(__name__)

def process_alert(cs_client, owner, repo, alert):
    """Process individual alert."""
    try:
        alert_number = alert['number']
        severity = alert['rule'].get('severity')
        
        # Example: Auto-assign based on severity
        if severity == 'critical':
            cs_client.update_alert(
                owner, repo, alert_number,
                state='open',
                assignees=['security-team']
            )
            return {"status": "assigned", "alert": alert_number}
        
        return {"status": "skipped", "alert": alert_number}
        
    except Exception as e:
        logger.error(f"Failed to process alert {alert['number']}: {e}")
        return {"status": "error", "alert": alert['number'], "error": str(e)}

def bulk_process_alerts(owner, repo, state="open", max_workers=10):
    """Process alerts in parallel."""
    
    rest, cs = create_clients()
    
    # Get all alerts
    alerts = cs.list_alerts_for_repo(owner, repo, state=state)
    logger.info(f"Processing {len(alerts)} alerts")
    
    results = {"assigned": 0, "skipped": 0, "error": 0}
    
    # Process in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        futures = {
            executor.submit(process_alert, cs, owner, repo, alert): alert
            for alert in alerts
        }
        
        # Collect results
        for future in as_completed(futures):
            result = future.result()
            results[result["status"]] += 1
            
            if result["status"] == "assigned":
                logger.info(f"Assigned alert {result['alert']}")
            elif result["status"] == "error":
                logger.error(f"Error in alert {result['alert']}: {result['error']}")
    
    logger.info(f"Bulk processing complete: {results}")
    return results

# Usage
results = bulk_process_alerts("myorg", "myrepo", max_workers=5)
```

### Policy Enforcement

**Dismissal Policy Enforcement**

```python
import re
from typing import Optional

class DismissalPolicy:
    """Enforce organizational dismissal policies."""
    
    def __init__(self):
        # Require ticket reference in all dismissals
        self.ticket_pattern = re.compile(r'(SEC|RISK|TICKET)-\d+')
        
        # Minimum comment length
        self.min_comment_length = 50
        
        # Approval required for certain CWEs
        self.approval_required_cwes = ['CWE-89', 'CWE-78', 'CWE-79']
    
    def validate_dismissal(
        self,
        alert: dict,
        reason: str,
        comment: str,
        approver: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """Validate dismissal against policy.
        
        Returns:
            (is_valid, error_message)
        """
        
        # Check comment length
        if len(comment) < self.min_comment_length:
            return False, f"Comment must be at least {self.min_comment_length} characters"
        
        # Check for ticket reference
        if not self.ticket_pattern.search(comment):
            return False, "Dismissal comment must include ticket reference (e.g., SEC-1042)"
        
        # Check if approval required
        cwe_tags = alert['rule'].get('tags', [])
        requires_approval = any(
            cwe in self.approval_required_cwes
            for cwe in cwe_tags
        )
        
        if requires_approval and not approver:
            return False, f"Dismissal requires security team approval for CWE tags: {cwe_tags}"
        
        # Check reason validity for severity
        severity = alert['rule'].get('severity')
        if severity == 'critical' and reason != 'false positive':
            return False, "Critical alerts can only be dismissed as 'false positive'"
        
        return True, None

def policy_compliant_dismissal(cs_client, owner, repo, alert_number, reason, comment, approver=None):
    """Dismiss alert with policy validation."""
    
    policy = DismissalPolicy()
    
    # Get alert details
    alert = cs_client.get_alert(owner, repo, alert_number)
    
    # Validate against policy
    is_valid, error = policy.validate_dismissal(alert, reason, comment, approver)
    
    if not is_valid:
        raise ValueError(f"Policy violation: {error}")
    
    # Add approval info to comment if provided
    if approver:
        comment = f"{comment}\n\nApproved by: @{approver}"
    
    # Dismiss alert
    return cs_client.dismiss_alert(owner, repo, alert_number, reason, comment)

# Usage
try:
    result = policy_compliant_dismissal(
        cs, "myorg", "myrepo", 42,
        reason="false positive",
        comment="Input validation prevents exploitation. Verified with security team review. Ticket: SEC-1042",
        approver="security-lead"
    )
    print("Alert dismissed with policy compliance")
except ValueError as e:
    print(f"Policy violation: {e}")
```

### Custom Workflows

**SLA Tracking Workflow**

```python
from datetime import datetime, timedelta
from enum import Enum

class SLAStatus(Enum):
    COMPLIANT = "compliant"
    AT_RISK = "at_risk"
    BREACHED = "breached"

class SLATracker:
    """Track alert SLA compliance."""
    
    # SLA targets (in days)
    SLA_TARGETS = {
        "critical": 1,
        "high": 7,
        "medium": 30,
        "low": 90
    }
    
    # Warning threshold (percentage of SLA)
    WARNING_THRESHOLD = 0.8
    
    def calculate_sla_status(self, alert: dict) -> dict:
        """Calculate SLA status for an alert."""
        
        severity = alert['rule'].get('severity', 'medium')
        sla_days = self.SLA_TARGETS.get(severity, 30)
        
        # Parse created_at
        created_at = datetime.fromisoformat(
            alert['created_at'].replace('Z', '+00:00')
        )
        
        # Calculate age and remaining time
        now = datetime.now(created_at.tzinfo)
        age_days = (now - created_at).days
        remaining_days = sla_days - age_days
        
        # Determine status
        if remaining_days < 0:
            status = SLAStatus.BREACHED
        elif age_days >= (sla_days * self.WARNING_THRESHOLD):
            status = SLAStatus.AT_RISK
        else:
            status = SLAStatus.COMPLIANT
        
        return {
            "alert_number": alert['number'],
            "severity": severity,
            "created_at": alert['created_at'],
            "age_days": age_days,
            "sla_days": sla_days,
            "remaining_days": remaining_days,
            "status": status.value,
            "compliance_percentage": (remaining_days / sla_days) * 100 if remaining_days >= 0 else 0
        }
    
    def get_sla_report(self, cs_client, owner, repo):
        """Generate SLA report for repository."""
        
        alerts = cs_client.list_alerts_for_repo(owner, repo, state="open")
        
        report = {
            "total_alerts": len(alerts),
            "by_severity": {},
            "by_status": {
                "compliant": 0,
                "at_risk": 0,
                "breached": 0
            },
            "alerts": []
        }
        
        for alert in alerts:
            sla_info = self.calculate_sla_status(alert)
            report["alerts"].append(sla_info)
            
            # Update counters
            severity = sla_info["severity"]
            status = sla_info["status"]
            
            if severity not in report["by_severity"]:
                report["by_severity"][severity] = {
                    "total": 0,
                    "compliant": 0,
                    "at_risk": 0,
                    "breached": 0
                }
            
            report["by_severity"][severity]["total"] += 1
            report["by_severity"][severity][status] += 1
            report["by_status"][status] += 1
        
        return report

# Usage
from code_scanning_api import create_clients

rest, cs = create_clients()
tracker = SLATracker()

report = tracker.get_sla_report(cs, "myorg", "myrepo")

print(f"Total open alerts: {report['total_alerts']}")
print(f"SLA breached: {report['by_status']['breached']}")
print(f"SLA at risk: {report['by_status']['at_risk']}")
print(f"SLA compliant: {report['by_status']['compliant']}")

# Alert on breached SLAs
breached = [a for a in report['alerts'] if a['status'] == 'breached']
if breached:
    print(f"\n⚠️  {len(breached)} alerts have breached SLA:")
    for alert in breached:
        print(f"  - Alert #{alert['alert_number']}: {alert['severity']} severity, "
              f"{alert['age_days']} days old (SLA: {alert['sla_days']} days)")
```

### Multi-Repository Operations

**Organization-Wide Alert Scanning**

```python
import asyncio
from code_scanning_api import create_async_clients

async def scan_organization(org: str, repos: list[str]):
    """Scan all repositories in an organization."""
    
    rest, cs = await create_async_clients()
    
    try:
        # Scan all repos concurrently
        tasks = [
            cs.list_alerts_for_repo(org, repo, state="open")
            for repo in repos
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Aggregate results
        org_report = {
            "organization": org,
            "total_repositories": len(repos),
            "total_alerts": 0,
            "by_severity": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0
            },
            "by_repository": {}
        }
        
        for repo, result in zip(repos, results):
            if isinstance(result, Exception):
                org_report["by_repository"][repo] = {
                    "status": "error",
                    "error": str(result)
                }
                continue
            
            # Count alerts by severity
            repo_stats = {
                "total": len(result),
                "by_severity": {
                    "critical": 0,
                    "high": 0,
                    "medium": 0,
                    "low": 0
                }
            }
            
            for alert in result:
                severity = alert['rule'].get('severity', 'low')
                repo_stats["by_severity"][severity] += 1
                org_report["by_severity"][severity] += 1
            
            org_report["by_repository"][repo] = repo_stats
            org_report["total_alerts"] += repo_stats["total"]
        
        return org_report
        
    finally:
        await rest.close()

# Get organization repositories (example using PyGithub)
from github import Github

g = Github("ghp_your_token")
org = g.get_organization("myorg")
repos = [repo.name for repo in org.get_repos()]

# Scan organization
report = asyncio.run(scan_organization("myorg", repos))

print(f"Organization: {report['organization']}")
print(f"Repositories scanned: {report['total_repositories']}")
print(f"Total alerts: {report['total_alerts']}")
print(f"\nBy severity:")
for severity, count in report['by_severity'].items():
    print(f"  {severity}: {count}")
```

---

## Deployment

### Docker Deployment

**Dockerfile**

```dockerfile
# Multi-stage build for minimal image size
FROM python:3.11-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY src/ ./src/
COPY scripts/ ./scripts/

# Make sure scripts are in PATH
ENV PATH=/root/.local/bin:$PATH

# Create non-root user
RUN useradd -m -u 1000 ghas && \
    chown -R ghas:ghas /app

USER ghas

# Default command
CMD ["python", "-m", "ghas_toolkit"]
```

**docker-compose.yml**

```yaml
version: '3.8'

services:
  ghas-toolkit:
    build: .
    image: ghas-toolkit:latest
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - LOG_LEVEL=INFO
      - LOG_FORMAT=json
    volumes:
      - ./config:/app/config:ro
      - ./output:/app/output
    command: ["python", "scripts/daily_report.py"]
    restart: unless-stopped
    
  # Webhook handler service
  webhook-handler:
    build: .
    image: ghas-toolkit:latest
    ports:
      - "8080:8080"
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - GITHUB_WEBHOOK_SECRET=${WEBHOOK_SECRET}
      - LOG_LEVEL=INFO
    command: ["python", "scripts/webhook_server.py"]
    restart: unless-stopped
    
  # Scheduled alert sync
  alert-sync:
    build: .
    image: ghas-toolkit:latest
    environment:
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - SERVICENOW_INSTANCE=${SNOW_INSTANCE}
      - SERVICENOW_USERNAME=${SNOW_USER}
      - SERVICENOW_PASSWORD=${SNOW_PASS}
    command: ["python", "scripts/servicenow_sync.py"]
    restart: unless-stopped
```

**Running with Docker**

```bash
# Build image
docker build -t ghas-toolkit:latest .

# Run one-off command
docker run --rm \
  -e GITHUB_TOKEN="${GITHUB_TOKEN}" \
  ghas-toolkit:latest \
  python -m ghas_toolkit list-alerts --owner myorg --repo myrepo

# Run with docker-compose
docker-compose up -d

# View logs
docker-compose logs -f ghas-toolkit

# Stop services
docker-compose down
```

### Kubernetes Deployment

**Deployment Manifest**

```yaml
# ghas-toolkit-deployment.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ghas-toolkit

---
apiVersion: v1
kind: Secret
metadata:
  name: ghas-credentials
  namespace: ghas-toolkit
type: Opaque
stringData:
  github-token: "ghp_your_token_here"
  webhook-secret: "your_webhook_secret"

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: ghas-config
  namespace: ghas-toolkit
data:
  LOG_LEVEL: "INFO"
  LOG_FORMAT: "json"

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ghas-webhook-handler
  namespace: ghas-toolkit
spec:
  replicas: 2
  selector:
    matchLabels:
      app: ghas-webhook-handler
  template:
    metadata:
      labels:
        app: ghas-webhook-handler
    spec:
      containers:
      - name: webhook-handler
        image: ghcr.io/your-org/ghas-toolkit:1.0.0
        ports:
        - containerPort: 8080
        env:
        - name: GITHUB_TOKEN
          valueFrom:
            secretKeyRef:
              name: ghas-credentials
              key: github-token
        - name: GITHUB_WEBHOOK_SECRET
          valueFrom:
            secretKeyRef:
              name: ghas-credentials
              key: webhook-secret
        envFrom:
        - configMapRef:
            name: ghas-config
        command: ["python", "scripts/webhook_server.py"]
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: ghas-webhook-handler
  namespace: ghas-toolkit
spec:
  selector:
    app: ghas-webhook-handler
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8080
  type: LoadBalancer

---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ghas-daily-report
  namespace: ghas-toolkit
spec:
  schedule: "0 9 * * 1-5"  # Weekdays at 9 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: report-generator
            image: ghcr.io/your-org/ghas-toolkit:1.0.0
            env:
            - name: GITHUB_TOKEN
              valueFrom:
                secretKeyRef:
                  name: ghas-credentials
                  key: github-token
            envFrom:
            - configMapRef:
                name: ghas-config
            command:
            - python
            - scripts/generate_org_report.py
            - --organization
            - myorg
            - --output
            - /output/report.html
            volumeMounts:
            - name: output
              mountPath: /output
          volumes:
          - name: output
            persistentVolumeClaim:
              claimName: ghas-output
          restartPolicy: OnFailure
```

**Deploying to Kubernetes**

```bash
# Apply manifests
kubectl apply -f ghas-toolkit-deployment.yaml

# Check deployment status
kubectl get pods -n ghas-toolkit

# View logs
kubectl logs -n ghas-toolkit -l app=ghas-webhook-handler -f

# Scale deployment
kubectl scale deployment ghas-webhook-handler --replicas=3 -n ghas-toolkit

# Update configuration
kubectl edit configmap ghas-config -n ghas-toolkit
kubectl rollout restart deployment ghas-webhook-handler -n ghas-toolkit
```

### AWS Lambda Deployment

**Lambda Handler**

```python
# lambda_handler.py
import json
import os
from code_scanning_api import create_clients

def lambda_handler(event, context):
    """AWS Lambda handler for GHAS operations."""
    
    # Parse event
    if 'body' in event:
        # API Gateway event
        body = json.loads(event['body'])
    else:
        # Direct invocation
        body = event
    
    operation = body.get('operation')
    owner = body.get('owner')
    repo = body.get('repo')
    
    # Initialize clients
    rest, cs = create_clients()
    
    try:
        if operation == 'list_alerts':
            alerts = cs.list_alerts_for_repo(
                owner=owner,
                repo=repo,
                state=body.get('state', 'open')
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'alerts': len(alerts),
                    'data': alerts
                })
            }
            
        elif operation == 'dismiss_alert':
            alert_number = body.get('alert_number')
            reason = body.get('reason')
            comment = body.get('comment')
            
            result = cs.dismiss_alert(
                owner=owner,
                repo=repo,
                alert_number=alert_number,
                reason=reason,
                comment=comment
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'dismissed',
                    'alert': result
                })
            }
            
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': f'Unknown operation: {operation}'
                })
            }
            
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
```

**Deployment Package**

```bash
# Create deployment package
mkdir lambda-package
cd lambda-package

# Install dependencies
pip install -t . ghas-code-scanning-toolkit

# Add handler
cp ../lambda_handler.py .

# Create ZIP
zip -r ../lambda-deployment.zip .

# Upload to Lambda
aws lambda create-function \
  --function-name ghas-alert-handler \
  --runtime python3.11 \
  --role arn:aws:iam::ACCOUNT:role/lambda-execution-role \
  --handler lambda_handler.lambda_handler \
  --zip-file fileb://../lambda-deployment.zip \
  --timeout 60 \
  --memory-size 512 \
  --environment Variables="{GITHUB_TOKEN=ghp_xxx}"
```

**SAM Template**

```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  GHASAlertHandler:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: ghas-alert-handler
      Runtime: python3.11
      Handler: lambda_handler.lambda_handler
      CodeUri: lambda-package/
      Timeout: 60
      MemorySize: 512
      Environment:
        Variables:
          GITHUB_TOKEN: !Ref GitHubToken
      Events:
        ApiEvent:
          Type: Api
          Properties:
            Path: /alerts
            Method: post
  
  DailyReportFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: ghas-daily-report
      Runtime: python3.11
      Handler: report_handler.lambda_handler
      CodeUri: lambda-package/
      Timeout: 300
      MemorySize: 1024
      Environment:
        Variables:
          GITHUB_TOKEN: !Ref GitHubToken
      Events:
        DailySchedule:
          Type: Schedule
          Properties:
            Schedule: cron(0 9 * * ? *)  # Daily at 9 AM UTC

Parameters:
  GitHubToken:
    Type: String
    NoEcho: true
    Description: GitHub Personal Access Token

Outputs:
  ApiUrl:
    Description: API Gateway endpoint URL
    Value: !Sub 'https://${ServerlessRestApi}.execute-api.${AWS::Region}.amazonaws.com/Prod/alerts'
```

**Deploy with SAM**

```bash
# Build
sam build

# Deploy
sam deploy --guided

# Invoke function
aws lambda invoke \
  --function-name ghas-alert-handler \
  --payload '{"operation":"list_alerts","owner":"myorg","repo":"myrepo"}' \
  response.json

cat response.json
```

---

## Examples

### Example 1: Daily Security Dashboard

```python
"""Generate daily security dashboard with metrics and charts."""

from code_scanning_api import create_clients
from collections import defaultdict
import json
from datetime import datetime

def generate_dashboard(owner: str, repo: str):
    """Generate comprehensive security dashboard."""
    
    rest, cs = create_clients()
    
    # Fetch all alerts
    all_alerts = cs.list_alerts_for_repo(owner, repo)
    open_alerts = cs.list_alerts_for_repo(owner, repo, state="open")
    
    # Calculate metrics
    metrics = {
        "generated_at": datetime.now().isoformat(),
        "repository": f"{owner}/{repo}",
        "total_alerts": len(all_alerts),
        "open_alerts": len(open_alerts),
        "dismissed_alerts": len([a for a in all_alerts if a['state'] == 'dismissed']),
        "fixed_alerts": len([a for a in all_alerts if a['state'] == 'fixed']),
    }
    
    # Breakdown by severity
    severity_counts = defaultdict(int)
    for alert in open_alerts:
        severity = alert['rule'].get('severity', 'unknown')
        severity_counts[severity] += 1
    
    metrics["by_severity"] = dict(severity_counts)
    
    # Breakdown by tool
    tool_counts = defaultdict(int)
    for alert in open_alerts:
        tool = alert['tool']['name']
        tool_counts[tool] += 1
    
    metrics["by_tool"] = dict(tool_counts)
    
    # Top 10 rules
    rule_counts = defaultdict(int)
    for alert in open_alerts:
        rule_id = alert['rule']['id']
        rule_counts[rule_id] += 1
    
    top_rules = sorted(
        rule_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:10]
    
    metrics["top_rules"] = [
        {"rule": rule, "count": count}
        for rule, count in top_rules
    ]
    
    # Assignment statistics
    assigned_count = len([a for a in open_alerts if a.get('assignees')])
    unassigned_count = len(open_alerts) - assigned_count
    
    metrics["assignment"] = {
        "assigned": assigned_count,
        "unassigned": unassigned_count,
        "percentage_assigned": (assigned_count / len(open_alerts) * 100) if open_alerts else 0
    }
    
    return metrics

# Generate and save dashboard
dashboard = generate_dashboard("myorg", "myrepo")

# Print summary
print(f"Dashboard generated at: {dashboard['generated_at']}")
print(f"Repository: {dashboard['repository']}")
print(f"\nAlert Summary:")
print(f"  Total: {dashboard['total_alerts']}")
print(f"  Open: {dashboard['open_alerts']}")
print(f"  Dismissed: {dashboard['dismissed_alerts']}")
print(f"  Fixed: {dashboard['fixed_alerts']}")

print(f"\nOpen Alerts by Severity:")
for severity, count in dashboard['by_severity'].items():
    print(f"  {severity}: {count}")

print(f"\nAssignment Status:")
print(f"  Assigned: {dashboard['assignment']['assigned']}")
print(f"  Unassigned: {dashboard['assignment']['unassigned']}")
print(f"  Coverage: {dashboard['assignment']['percentage_assigned']:.1f}%")

# Save to file
with open('dashboard.json', 'w') as f:
    json.dump(dashboard, f, indent=2)
```

### Example 2: Auto-Triage Bot

```python
"""Automated alert triage based on rules."""

from code_scanning_api import create_clients
import re

class AutoTriageBot:
    """Automated alert triage bot."""
    
    def __init__(self, cs_client):
        self.cs = cs_client
        
        # Define triage rules
        self.rules = [
            {
                "name": "Auto-dismiss test code alerts",
                "condition": self.is_test_code,
                "action": self.dismiss_as_test_code
            },
            {
                "name": "Auto-assign critical SQL injection",
                "condition": self.is_critical_sql_injection,
                "action": self.assign_to_database_team
            },
            {
                "name": "Auto-assign XSS to frontend team",
                "condition": self.is_xss_alert,
                "action": self.assign_to_frontend_team
            },
        ]
    
    def is_test_code(self, alert: dict) -> bool:
        """Check if alert is in test code."""
        location = alert.get('most_recent_instance', {}).get('location', {})
        path = location.get('path', '')
        
        test_patterns = [
            r'/test/',
            r'/tests/',
            r'_test\.py$',
            r'\.test\.js$',
            r'/spec/',
        ]
        
        return any(re.search(pattern, path) for pattern in test_patterns)
    
    def is_critical_sql_injection(self, alert: dict) -> bool:
        """Check if alert is critical SQL injection."""
        return (
            alert['rule'].get('severity') == 'critical' and
            'sql-injection' in alert['rule']['id'].lower()
        )
    
    def is_xss_alert(self, alert: dict) -> bool:
        """Check if alert is XSS."""
        cwe_tags = alert['rule'].get('tags', [])
        return 'CWE-79' in cwe_tags
    
    def dismiss_as_test_code(self, owner: str, repo: str, alert: dict):
        """Dismiss alert as test code."""
        return self.cs.dismiss_alert(
            owner=owner,
            repo=repo,
            alert_number=alert['number'],
            reason="used in tests",
            comment=f"Auto-triaged: Alert in test code path. "
                    f"File: {alert.get('most_recent_instance', {}).get('location', {}).get('path')}. "
                    f"Not reachable in production."
        )
    
    def assign_to_database_team(self, owner: str, repo: str, alert: dict):
        """Assign to database team."""
        return self.cs.update_alert(
            owner=owner,
            repo=repo,
            alert_number=alert['number'],
            state='open',
            assignees=['database-team', 'security-team']
        )
    
    def assign_to_frontend_team(self, owner: str, repo: str, alert: dict):
        """Assign to frontend team."""
        return self.cs.update_alert(
            owner=owner,
            repo=repo,
            alert_number=alert['number'],
            state='open',
            assignees=['frontend-team', 'xss-specialist']
        )
    
    def triage_alerts(self, owner: str, repo: str):
        """Run triage rules on all open alerts."""
        
        # Get open, unassigned alerts
        alerts = self.cs.list_alerts_for_repo(
            owner=owner,
            repo=repo,
            state="open",
            assignees="none"
        )
        
        results = {
            "processed": 0,
            "dismissed": 0,
            "assigned": 0,
            "unchanged": 0,
            "errors": 0
        }
        
        for alert in alerts:
            try:
                # Check each rule
                for rule in self.rules:
                    if rule["condition"](alert):
                        print(f"Alert {alert['number']}: Applying rule '{rule['name']}'")
                        
                        result = rule["action"](owner, repo, alert)
                        
                        if result['state'] == 'dismissed':
                            results["dismissed"] += 1
                        elif result.get('assignees'):
                            results["assigned"] += 1
                        
                        results["processed"] += 1
                        break  # Only apply first matching rule
                else:
                    results["unchanged"] += 1
                    
            except Exception as e:
                print(f"Error processing alert {alert['number']}: {e}")
                results["errors"] += 1
        
        return results

# Usage
rest, cs = create_clients()
bot = AutoTriageBot(cs)

results = bot.triage_alerts("myorg", "myrepo")

print(f"\nTriage Results:")
print(f"  Processed: {results['processed']}")
print(f"  Dismissed: {results['dismissed']}")
print(f"  Assigned: {results['assigned']}")
print(f"  Unchanged: {results['unchanged']}")
print(f"  Errors: {results['errors']}")
```

### Example 3: Alert Export to CSV

```python
"""Export alerts to CSV for analysis."""

import csv
from code_scanning_api import create_clients
from datetime import datetime

def export_alerts_to_csv(owner: str, repo: str, filename: str = "alerts.csv"):
    """Export all alerts to CSV file."""
    
    rest, cs = create_clients()
    
    # Fetch all alerts
    alerts = cs.list_alerts_for_repo(owner, repo)
    
    # Define CSV columns
    fieldnames = [
        'alert_number',
        'state',
        'severity',
        'rule_id',
        'rule_description',
        'tool_name',
        'cwe_tags',
        'file_path',
        'line_number',
        'created_at',
        'updated_at',
        'dismissed_by',
        'dismissed_reason',
        'dismissed_comment',
        'assignees',
        'html_url'
    ]
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for alert in alerts:
            # Extract location info
            location = alert.get('most_recent_instance', {}).get('location', {})
            
            # Format assignees
            assignees = ', '.join([
                a['login'] for a in alert.get('assignees', [])
            ])
            
            # Format CWE tags
            cwe_tags = ', '.join(alert['rule'].get('tags', []))
            
            row = {
                'alert_number': alert['number'],
                'state': alert['state'],
                'severity': alert['rule'].get('severity', ''),
                'rule_id': alert['rule']['id'],
                'rule_description': alert['rule']['description'],
                'tool_name': alert['tool']['name'],
                'cwe_tags': cwe_tags,
                'file_path': location.get('path', ''),
                'line_number': location.get('start_line', ''),
                'created_at': alert['created_at'],
                'updated_at': alert['updated_at'],
                'dismissed_by': alert.get('dismissed_by', {}).get('login', ''),
                'dismissed_reason': alert.get('dismissed_reason', ''),
                'dismissed_comment': alert.get('dismissed_comment', ''),
                'assignees': assignees,
                'html_url': alert['html_url']
            }
            
            writer.writerow(row)
    
    print(f"Exported {len(alerts)} alerts to {filename}")

# Export alerts
export_alerts_to_csv("myorg", "myrepo", "security-alerts.csv")
```

---

## Troubleshooting

### Common Issues and Solutions

#### Issue: 401 Unauthorized

**Symptoms:**
```
GitHubAuthError: 401 Unauthorized: Bad credentials
```

**Possible Causes:**
1. Token is invalid or expired
2. Token not set in environment
3. Wrong token for GHES instance

**Solutions:**

```bash
# Check if token is set
echo $GITHUB_TOKEN

# Verify token with GitHub CLI
gh auth status

# Test token manually
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# Regenerate token if needed
# Navigate to: https://github.com/settings/tokens

# For GHES, ensure correct hostname
export GITHUB_HOSTNAME="github.example.com"
gh auth login --hostname github.example.com
```

#### Issue: 403 Forbidden

**Symptoms:**
```
GitHubApiError: 403 Forbidden: Resource not accessible by integration
```

**Possible Causes:**
1. Missing token permissions/scopes
2. GitHub Advanced Security not enabled
3. Repository is archived
4. Fine-grained PAT lacks required permissions

**Solutions:**

```python
# Check token scopes
import requests

response = requests.get(
    "https://api.github.com/user",
    headers={
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }
)

scopes = response.headers.get('X-OAuth-Scopes', '').split(', ')
print(f"Token scopes: {scopes}")

# Required scopes:
# - security_events (Code Scanning)
# - repo (for autofixes)
```

**Verify GHAS is enabled:**

```bash
# Check if GHAS is enabled for repository
gh api /repos/OWNER/REPO | jq '.security_and_analysis'
```

#### Issue: 404 Not Found

**Symptoms:**
```
GitHubNotFoundError: 404 Not Found
```

**Possible Causes:**
1. Repository doesn't exist or is inaccessible
2. Alert number doesn't exist
3. Endpoint not available on GHES version
4. GHAS not enabled (sometimes returns 404 instead of 403)

**Solutions:**

```bash
# Verify repository exists
gh repo view OWNER/REPO

# List actual alerts to verify alert numbers
gh api /repos/OWNER/REPO/code-scanning/alerts

# Check GHES version
gh api /meta | jq '.installed_version'

# Verify GHAS is enabled
gh api /repos/OWNER/REPO | jq '.security_and_analysis.advanced_security.status'
```

#### Issue: Rate Limit Exceeded

**Symptoms:**
```
GitHubRateLimitError: 429 Too Many Requests
```

**Solutions:**

```python
# Check current rate limit status
from code_scanning_api import create_clients

rest, cs = create_clients()

response = rest.request("GET", "/rate_limit")
core = response['resources']['core']

print(f"Limit: {core['limit']}")
print(f"Remaining: {core['remaining']}")
print(f"Resets at: {datetime.fromtimestamp(core['reset'])}")

# Wait for reset
import time

if core['remaining'] == 0:
    wait_seconds = core['reset'] - time.time() + 1
    print(f"Waiting {wait_seconds:.0f} seconds for rate limit reset...")
    time.sleep(wait_seconds)
```

**Prevention:**

```python
# Use higher rate limit token (GitHub App)
# Implement request caching
# Add delays between bulk operations

import time

for alert_number in alert_numbers:
    cs.dismiss_alert(owner, repo, alert_number, ...)
    time.sleep(0.5)  # 500ms delay between requests
```

#### Issue: Autofix Not Available

**Symptoms:**
```
GitHubApiError: 422 Unprocessable Entity
```

**Possible Causes:**
1. Alert type doesn't support autofix
2. Autofix feature not enabled
3. No autofix available for this vulnerability

**Solutions:**

```python
# Check autofix status first
status = cs.get_autofix_status(owner, repo, alert_number)

if status == "not_available":
    print(f"Autofix not supported for alert {alert_number}")
    # Continue without autofix
else:
    # Proceed with autofix
    cs.create_autofix(owner, repo, alert_number)
```

#### Issue: Pagination Incomplete

**Symptoms:**
- Only receiving first 100 alerts
- Missing data in bulk operations

**Cause:**
Not using paginated request method

**Solution:**

```python
# WRONG - only gets first page (max 100 results)
response = rest.request("GET", "/repos/owner/repo/code-scanning/alerts")

# CORRECT - follows pagination to completion
all_alerts = rest.request_paginated("GET", "/repos/owner/repo/code-scanning/alerts")
```

#### Issue: Connection Timeouts

**Symptoms:**
```
requests.exceptions.Timeout: HTTPSConnectionPool
```

**Solutions:**

```python
# Increase timeout
rest = GitHubRestClient(
    token="ghp_xxx",
    timeout_s=60.0  # Increase from default 30s
)

# Retry with exponential backoff (already built-in)
rest = GitHubRestClient(
    token="ghp_xxx",
    max_retries=10,  # Increase retries
    max_backoff_s=60.0  # Allow longer backoff
)
```

#### Issue: SSL Certificate Verification Failures

**Symptoms:**
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Cause:**
GHES with self-signed certificate or corporate proxy

**Solution (not recommended for production):**

```python
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# In requests, use verify=False
# NOTE: Only for testing, not production
```

**Better Solution:**

```bash
# Add CA certificate to system trust store
# Or set certificate bundle
export REQUESTS_CA_BUNDLE=/path/to/ca-bundle.crt
```

### Debug Mode

Enable verbose logging for troubleshooting:

```python
import logging

# Enable DEBUG logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# This will show:
# - All HTTP requests and responses
# - Retry attempts
# - Rate limit headers
# - Error details

from code_scanning_api import create_clients

rest, cs = create_clients()
alerts = cs.list_alerts_for_repo("myorg", "myrepo")
```

### Getting Support

**GitHub Support Ticket**

When opening a GitHub Support ticket, include:
1. `X-GitHub-Request-Id` from error (available in exceptions)
2. Exact timestamp of request
3. Repository owner and name
4. Alert number (if applicable)
5. Token type (Classic PAT, fine-grained PAT, GitHub App)

```python
from code_scanning_api import GitHubApiError

try:
    alert = cs.get_alert("myorg", "myrepo", 42)
except GitHubApiError as e:
    print(f"Request ID for support ticket: {e.request_id}")
```

---

## Development

### Project Structure

```
ghas-code-scanning-toolkit/
├── src/
│   └── ghas_toolkit/
│       ├── __init__.py
│       ├── rest.py              # GitHubRestClient
│       ├── code_scanning.py      # CodeScanningClient
│       ├── async_client.py       # Async support
│       ├── exceptions.py         # Exception classes
│       └── utils.py              # Helper functions
├── scripts/
│   ├── webhook_server.py         # Webhook handler
│   ├── servicenow_sync.py        # ServiceNow integration
│   ├── generate_report.py        # Report generation
│   └── cli.py                    # CLI interface
├── tests/
│   ├── __init__.py
│   ├── test_rest.py
│   ├── test_code_scanning.py
│   ├── test_async.py
│   └── test_integration.py
├── docs/
│   ├── api.md
│   ├── examples.md
│   └── deployment.md
├── .github/
│   └── workflows/
│       ├── ci.yml                # CI pipeline
│       ├── release.yml           # Release automation
│       └── security.yml          # Security scanning
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── CHANGELOG.md
├── LICENSE
└── CONTRIBUTING.md
```

### Testing

**Run Tests**

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/ghas_toolkit --cov-report=html

# Run specific test file
pytest tests/test_code_scanning.py

# Run with verbose output
pytest -v

# Run only integration tests
pytest -m integration
```

**Writing Tests**

```python
# tests/test_code_scanning.py
import pytest
from ghas_toolkit import CodeScanningClient, GitHubRestClient
from unittest.mock import Mock, patch

class TestCodeScanningClient:
    """Tests for CodeScanningClient."""
    
    @pytest.fixture
    def mock_rest_client(self):
        """Create mock REST client."""
        return Mock(spec=GitHubRestClient)
    
    @pytest.fixture
    def cs_client(self, mock_rest_client):
        """Create CodeScanningClient with mock."""
        return CodeScanningClient(mock_rest_client)
    
    def test_list_alerts(self, cs_client, mock_rest_client):
        """Test listing alerts."""
        # Setup mock
        mock_rest_client.request_paginated.return_value = [
            {"number": 1, "state": "open"},
            {"number": 2, "state": "open"}
        ]
        
        # Execute
        alerts = cs_client.list_alerts_for_repo("myorg", "myrepo")
        
        # Assert
        assert len(alerts) == 2
        mock_rest_client.request_paginated.assert_called_once()
    
    def test_dismiss_alert(self, cs_client, mock_rest_client):
        """Test dismissing alert."""
        mock_rest_client.request.return_value = {
            "number": 42,
            "state": "dismissed",
            "dismissed_reason": "false positive"
        }
        
        result = cs_client.dismiss_alert(
            "myorg", "myrepo", 42,
            reason="false positive",
            comment="Test dismissal"
        )
        
        assert result["state"] == "dismissed"
        assert result["dismissed_reason"] == "false positive"
```

### Code Quality

**Formatting with Black**

```bash
# Format code
black src/ tests/

# Check formatting
black --check src/ tests/
```

**Linting with Ruff**

```bash
# Run linter
ruff check src/ tests/

# Auto-fix issues
ruff check --fix src/ tests/
```

**Type Checking with mypy**

```bash
# Run type checker
mypy src/

# Strict mode
mypy --strict src/
```

**Pre-commit Hooks**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black
  
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.9
    hooks:
      - id: ruff
        args: [--fix]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.7.1
    hooks:
      - id: mypy
        additional_dependencies: [types-requests]
```

### Release Process

**Version Bumping**

```bash
# Install bump2version
pip install bump2version

# Bump patch version (1.0.0 -> 1.0.1)
bump2version patch

# Bump minor version (1.0.1 -> 1.1.0)
bump2version minor

# Bump major version (1.1.0 -> 2.0.0)
bump2version major
```

**Creating a Release**

```bash
# Create release tag
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0

# GitHub Actions will automatically:
# 1. Run tests
# 2. Build package
# 3. Publish to PyPI
# 4. Create GitHub Release
```

**Manual PyPI Release**

```bash
# Build package
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

### Quick Start for Contributors

```bash
# Fork the repository on GitHub

# Clone your fork
git clone https://github.com/YOUR-USERNAME/ghas-code-scanning-toolkit.git
cd ghas-code-scanning-toolkit

# Add upstream remote
git remote add upstream https://github.com/original-org/ghas-code-scanning-toolkit.git

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install development dependencies
pip install -e ".[dev,test]"

# Install pre-commit hooks
pre-commit install

# Create feature branch
git checkout -b feature/your-feature-name

# Make changes and commit
git add .
git commit -m "feat: add new feature"

# Run tests
pytest

# Push to your fork
git push origin feature/your-feature-name

# Open Pull Request on GitHub
```

### Contribution Guidelines

**Code Standards**
- Follow PEP 8 style guide
- Use Black for formatting
- Include type hints for all functions
- Write docstrings for public APIs
- Add tests for new features

**Commit Messages**
Follow [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `test:` Test changes
- `refactor:` Code refactoring
- `chore:` Build/tooling changes

**Pull Request Process**
1. Update documentation for new features
2. Add tests for bug fixes
3. Ensure all tests pass
4. Update CHANGELOG.md
5. Get approval from maintainer

---

## Changelog

### [1.0.0] - 2024-01-18

**Added**
- Initial release
- GitHubRestClient with retry logic and rate limiting
- CodeScanningClient with full alert management
- Async support for high-performance operations
- ServiceNow integration patterns
- Webhook integration examples
- CI/CD integration templates
- Docker and Kubernetes deployment support
- Comprehensive documentation

**Changed**
- N/A (initial release)

**Deprecated**
- N/A (initial release)

**Removed**
- N/A (initial release)

**Fixed**
- N/A (initial release)

**Security**
- N/A (initial release)

---

## Security

### Reporting Security Issues

**DO NOT** open public issues for security vulnerabilities.

Email security concerns to: security@your-org.com

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Security Best Practices

**Token Management**
- Never commit tokens to version control
- Use environment variables or secret managers
- Rotate tokens regularly (every 90 days recommended)
- Use fine-grained PATs with minimal permissions
- Enable token expiration when possible

**Network Security**
- Use HTTPS for all API communication
- Validate SSL certificates
- Use corporate proxy if required
- Implement network egress controls

**Application Security**
- Validate all user inputs
- Sanitize data before logging
- Implement proper error handling
- Use principle of least privilege
- Enable security scanning in CI/CD

---

## License

MIT License

Copyright (c) 2024 Your Organization

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## Support

### Community Support

- **GitHub Discussions**: [github.com/your-org/ghas-code-scanning-toolkit/discussions](https://github.com/your-org/ghas-code-scanning-toolkit/discussions)
- **GitHub Issues**: [github.com/your-org/ghas-code-scanning-toolkit/issues](https://github.com/your-org/ghas-code-scanning-toolkit/issues)
- **Stack Overflow**: Tag questions with `ghas-toolkit`

### Enterprise Support

For enterprise support plans, contact: support@your-org.com

### Acknowledgments

- GitHub Advanced Security team for API documentation
- Contributors and maintainers
- Open source community

---

<div align="center">

**[⬆ Back to Top](#github-code-scanning-alert-manager)**

Made with ❤️ by the Security Engineering Team

</div>
