from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

VALID_STATUSES = {
    "SURVIVED",
    "BEND",
    "WEIRD",
    "BREAK",
    "CATASTROPHIC",
    "BLOCKED",
}

@dataclass(slots=True)
class SnapshotEntry:
    relative_path: str
    size: int
    sha256: str
    kind: str = "file"

@dataclass(slots=True)
class Finding:
    profile: str
    scenario: str
    status: str
    severity: str
    summary: str
    reproduction: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    suspected_cause: str = ""
    recommended_action: str = ""
    adapter: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALID_STATUSES:
            raise ValueError(f"Unknown finding status: {self.status}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class RunReport:
    run_id: str
    target: str
    profile: str
    started_utc: str
    finished_utc: str
    baseline_files: int
    baseline_bytes: int
    integrity_passed: bool
    integrity_diff: list[str]
    findings: list[Finding]
    sandbox_strategy: str = "disposable filesystem clone"
    adapter_names: list[str] = field(default_factory=list)
    target_kinds: list[str] = field(default_factory=list)
    adapter_capabilities: list[str] = field(default_factory=list)
    evidence_path: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["findings"] = [f.to_dict() for f in self.findings]
        return data