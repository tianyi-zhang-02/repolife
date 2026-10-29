"""Plain data types shared by the pipeline. The JSON report layout lives in report.py."""

from __future__ import annotations

from dataclasses import dataclass, field

# Bump when a field in the JSON report is renamed, removed or changes meaning.
# Adding new fields does not require a bump.
SCHEMA_VERSION = 1

STATUSES = ("ACTIVE", "STABLE", "DORMANT", "ORPHAN")


@dataclass
class FileRecord:
    path: str
    language: str
    kind: str  # "code" | "config" | "docs"
    code: int = 0
    comment: int = 0
    blank: int = 0

    # Reachability. `analyzer` names the plugin that covered this file; when no
    # plugin covers the language, `reachability` stays None rather than guessing.
    analyzer: str | None = None
    is_test: bool = False
    reachability: str | None = None  # "prod" | "test" | "none"
    inbound: int = 0
    roots: list[str] = field(default_factory=list)

    # Git activity.
    tracked: bool = False
    first_commit: str | None = None
    last_commit: str | None = None
    age_days: int | None = None
    commits_active: int = 0
    commits_year: int = 0
    authors_year: int = 0

    # Verdict.
    status: str | None = None  # one of STATUSES, "UNKNOWN" without git, None for non-code
    confidence: str | None = None  # only set for ORPHAN: "high" | "medium" | "low"
    notes: list[str] = field(default_factory=list)
