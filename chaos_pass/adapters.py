from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .models import Finding

@dataclass(slots=True)
class AdapterContext:
    original_target: Path
    sandbox_target: Path
    run_id: str
    metadata: dict[str, str] = field(default_factory=dict)

class ChaosAdapter(Protocol):
    name: str

    def supports(self, target: Path) -> bool:
        ...

    def expert_scenarios(self, context: AdapterContext) -> list[Finding]:
        ...

    def run_scenario(self, scenario: str, context: AdapterContext) -> list[Finding]:
        ...

    def collect_evidence(self, context: AdapterContext) -> list[str]:
        ...

    def verify_sandbox_only(self, context: AdapterContext) -> bool:
        ...
