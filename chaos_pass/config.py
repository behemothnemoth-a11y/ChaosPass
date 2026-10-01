from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import Any

@dataclass(slots=True)
class TargetConfig:
    data: dict[str, Any]
    source: Path | None

    @property
    def cli(self) -> dict[str, Any]:
        value = self.data.get("cli", {})
        return value if isinstance(value, dict) else {}

    @property
    def chaos(self) -> dict[str, Any]:
        value = self.data.get("chaospass", {})
        return value if isinstance(value, dict) else {}

def _candidate_paths(target: Path) -> list[Path]:
    root = target if target.is_dir() else target.parent
    return [
        root / "chaospass.toml",
        root / ".chaospass.toml",
    ]

def load_target_config(target: Path, explicit: Path | None = None) -> TargetConfig:
    candidates = [explicit] if explicit else _candidate_paths(target)
    for path in candidates:
        if path is None:
            continue
        resolved = path.expanduser().resolve()
        if not resolved.exists():
            if explicit:
                raise FileNotFoundError(f"Chaos Pass config not found: {resolved}")
            continue
        with resolved.open("rb") as handle:
            data = tomllib.load(handle)
        if not isinstance(data, dict):
            raise ValueError(f"{resolved}: TOML root must be a table")
        return TargetConfig(data=data, source=resolved)
    return TargetConfig(data={}, source=None)

def configured_probe_scenarios(config: TargetConfig) -> set[str]:
    scenarios: set[str] = set()
    probes = config.cli.get("probes", [])
    if not isinstance(probes, list):
        return scenarios
    for probe in probes:
        if isinstance(probe, dict) and isinstance(probe.get("scenario"), str):
            scenarios.add(probe["scenario"])
    return scenarios