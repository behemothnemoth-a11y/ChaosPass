from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable
import os

from .config import TargetConfig
from .models import Finding
from .processes import SandboxProcessRunner

SKIP_RECON_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".tox", ".mypy_cache"}

@dataclass(slots=True)
class TargetFingerprint:
    target: str
    path_kind: str
    file_count_sampled: int
    bytes_sampled: int
    extension_counts: dict[str, int]
    markers: list[str]
    target_kinds: list[str]
    scan_truncated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class AdapterAction:
    action_id: str
    description: str
    capability: str
    risk: str
    executable: bool
    source_adapter: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class AdapterPlan:
    profile: str
    adapter_names: list[str]
    target_kinds: list[str]
    capabilities: list[str]
    actions: list[AdapterAction]
    uncovered_surfaces: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "adapter_names": self.adapter_names,
            "target_kinds": self.target_kinds,
            "capabilities": self.capabilities,
            "actions": [a.to_dict() for a in self.actions],
            "auto_actions": [a.to_dict() for a in self.actions if a.executable],
            "driver_actions": [a.to_dict() for a in self.actions if not a.executable],
            "uncovered_surfaces": self.uncovered_surfaces,
        }

@dataclass(slots=True)
class AdapterContext:
    original_target: Path
    sandbox_target: Path
    run_id: str
    profile: str
    profile_definition: dict[str, Any]
    fingerprint: TargetFingerprint
    config: TargetConfig
    process_runner: SandboxProcessRunner
    metadata: dict[str, str] = field(default_factory=dict)

class BaseAdapter:
    name = "base"
    target_kind = "unknown"
    priority = 0
    capabilities: tuple[str, ...] = ()
    scenarios: tuple[str, ...] = ()

    def supports(self, fingerprint: TargetFingerprint, config: TargetConfig) -> bool:
        return False

    def can_handle(self, scenario: str) -> bool:
        return scenario in self.scenarios

    def can_handle_context(self, scenario: str, context: AdapterContext) -> bool:
        return self.can_handle(scenario)

    def plan(self, profile_definition: dict[str, Any]) -> list[AdapterAction]:
        return []

    def run_scenario(self, scenario: str, context: AdapterContext) -> list[Finding]:
        return []

def _walk_sample(target: Path, max_files: int) -> tuple[int, int, dict[str, int], bool]:
    if target.is_file():
        suffix = target.suffix.lower() or "<none>"
        return 1, target.stat().st_size, {suffix: 1}, False
    count = 0
    total = 0
    extensions: dict[str, int] = {}
    truncated = False
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_RECON_DIRS]
        for name in files:
            path = Path(root) / name
            try:
                size = path.stat().st_size
            except OSError:
                continue
            count += 1
            total += size
            suffix = path.suffix.lower() or "<none>"
            extensions[suffix] = extensions.get(suffix, 0) + 1
            if count >= max_files:
                truncated = True
                return count, total, extensions, truncated
    return count, total, extensions, truncated

def fingerprint_target(target: Path, config: TargetConfig, max_files: int = 5000) -> TargetFingerprint:
    target = target.resolve()
    root = target if target.is_dir() else target.parent
    marker_names = [
        ".git", "pyproject.toml", "setup.py", "requirements.txt",
        "package.json", "Cargo.toml", "pom.xml", "build.gradle",
        "gradlew", "chaospass.toml", ".chaospass.toml",
    ]
    markers = [name for name in marker_names if (root / name).exists()]
    count, total, extensions, truncated = _walk_sample(target, max_files)
    kinds = ["filesystem"]
    if (root / ".git").exists():
        kinds.append("git-repository")
    if any((root / name).exists() for name in ("pyproject.toml", "setup.py", "requirements.txt")):
        kinds.append("python-project")
    if (root / "package.json").exists():
        kinds.append("node-project")
    if (root / "Cargo.toml").exists():
        kinds.append("rust-project")
    if target.is_file() and target.suffix.lower() in {".exe", ".bat", ".cmd", ".ps1", ".py"}:
        kinds.append("executable-file")
    if config.cli:
        kinds.append("configured-cli")
    ordered_ext = dict(sorted(extensions.items(), key=lambda item: (-item[1], item[0]))[:20])
    return TargetFingerprint(
        target=str(target),
        path_kind="directory" if target.is_dir() else "file",
        file_count_sampled=count,
        bytes_sampled=total,
        extension_counts=ordered_ext,
        markers=markers,
        target_kinds=kinds,
        scan_truncated=truncated,
    )

class AdapterStack:
    def __init__(self, adapters: Iterable[BaseAdapter], fingerprint: TargetFingerprint) -> None:
        self.adapters = sorted(list(adapters), key=lambda a: (-a.priority, a.name))
        self.fingerprint = fingerprint

    @property
    def names(self) -> list[str]:
        return [a.name for a in self.adapters]

    @property
    def target_kinds(self) -> list[str]:
        kinds = list(self.fingerprint.target_kinds)
        for adapter in self.adapters:
            if adapter.target_kind and adapter.target_kind not in kinds:
                kinds.append(adapter.target_kind)
        return kinds

    @property
    def capabilities(self) -> list[str]:
        values = {cap for adapter in self.adapters for cap in adapter.capabilities}
        return sorted(values)

    def plan(self, profile_definition: dict[str, Any]) -> AdapterPlan:
        actions: list[AdapterAction] = []
        for adapter in self.adapters:
            actions.extend(adapter.plan(profile_definition))
        covered = {action.capability for action in actions}
        requested = [str(x) for x in profile_definition.get("attack_surface_priority", [])]
        uncovered = [surface for surface in requested if not any(surface.lower() in cap.lower() for cap in covered)]
        return AdapterPlan(
            profile=str(profile_definition.get("id", "unknown")),
            adapter_names=self.names,
            target_kinds=self.target_kinds,
            capabilities=self.capabilities,
            actions=actions,
            uncovered_surfaces=uncovered,
        )

    def run_scenario(self, scenario: str, context: AdapterContext) -> list[Finding]:
        handlers = [adapter for adapter in self.adapters if adapter.can_handle_context(scenario, context)]
        if not handlers:
            return [Finding(
                profile=context.profile,
                scenario=scenario,
                status="BLOCKED",
                severity="info",
                summary=f"No selected adapter can execute {scenario} safely for this target.",
                evidence=[f"adapters={','.join(self.names)}", f"capabilities={','.join(self.capabilities)}"],
                recommended_action="Add a target adapter or a chaospass.toml configured probe for this scenario.",
                adapter="adapter-stack",
            )]
        findings: list[Finding] = []
        for adapter in handlers:
            try:
                results = adapter.run_scenario(scenario, context)
            except Exception as exc:
                results = [Finding(
                    profile=context.profile,
                    scenario=scenario,
                    status="BREAK",
                    severity="high",
                    summary=f"Adapter {adapter.name} raised {type(exc).__name__}: {exc}",
                    suspected_cause="Adapter implementation failed while operating inside the disposable sandbox.",
                    recommended_action="Fix or constrain the adapter before relying on this probe.",
                    adapter=adapter.name,
                )]
            for finding in results:
                if not finding.adapter:
                    finding.adapter = adapter.name
            findings.extend(results)
        return findings

class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: list[BaseAdapter] = []

    def register(self, adapter: BaseAdapter) -> None:
        self._adapters.append(adapter)

    def resolve(self, fingerprint: TargetFingerprint, config: TargetConfig) -> AdapterStack:
        selected = [adapter for adapter in self._adapters if adapter.supports(fingerprint, config)]
        return AdapterStack(selected, fingerprint)

def default_registry() -> AdapterRegistry:
    from .builtin_adapters import builtin_adapters
    registry = AdapterRegistry()
    for adapter in builtin_adapters():
        registry.register(adapter)
    return registry

def discover_adapters(target: Path, config: TargetConfig) -> tuple[TargetFingerprint, AdapterStack]:
    fingerprint = fingerprint_target(target, config)
    return fingerprint, default_registry().resolve(fingerprint, config)