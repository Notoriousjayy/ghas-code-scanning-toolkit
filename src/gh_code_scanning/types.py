from __future__ import annotations
from typing import Literal

AlertState = Literal["open", "dismissed", "fixed", "closed"]
UpdateAlertState = Literal["open", "dismissed"]

Severity = Literal["critical", "high", "medium", "low", "warning", "note", "error"]
SortField = Literal["created", "updated"]
Direction = Literal["asc", "desc"]

# GitHub docs use these exact strings for dismissed_reason
DismissedReason = Literal["false positive", "won't fix", "used in tests"]
SortType = Literal["alerts", "created", "updated"]
SortDirection = Literal["asc", "desc"]
RepositoryVisibility = Literal["all", "public", "private", "internal"]
RepositoryAffiliation = Literal["owner", "collaborator", "organization_member"]
State = Literal["open", "closed", "all"]
LicenseType = Literal[
    "mit",
    "apache-2.0",
    "gpl-3.0",
    "bsd-2-clause",
    "bsd-3-clause",
    "lgpl-3.0",
    "mpl-2.0",
    "unlicense",
    "agpl-3.0",
    "epl-2.0",
    "cc0-1.0",
]
SortOrder = Literal["asc", "desc"]
IssueState = Literal["open", "closed", "all"]
PullRequestState = Literal["open", "closed", "all"]
MergeableState = Literal["clean", "dirty", "unknown", "unstable", "blocked"]
CheckStatus = Literal["queued", "in_progress", "completed"]
CheckConclusion = Literal[
    "success",
    "failure",
    "neutral",
    "cancelled",
    "timed_out",
    "action_required",
    "skipped",
    "stale",
]
RefType = Literal["branch", "tag"]
ContentState = Literal["active", "archived"]
ProjectState = Literal["open", "closed"]
