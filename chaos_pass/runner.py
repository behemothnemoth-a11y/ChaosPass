from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import random
import uuid

from .adapters import AdapterContext, discover_adapters
from .config import load_target_config
from .models import Finding, RunReport
from .processes import SandboxProcessRunner
from .profiles import load_profile_definition
from .safety import clone_target, diff_snapshots, snapshot_path, snapshot_size
from .scenarios import run_scenario

def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def _phase_names(profile: str) -> list[str]:
    if profile != "full-chaos-pass":
        return [profile]
    return [
        "expert-baseline",
        "power-user",
        "boundary-hunter",
        "wrong-way-user",
        "chaos-goblin",
        "ui-gremlin",
        "performance-murderer",
        "persistence-demon",
        "state-breaker",
        "charlie",
        "random-chaos",
        "wildcard",
        "soak-monster",
        "regression-archaeologist",
        "full-chaos-pass",
    ]

def _integrity_result(
    baseline,
    target: Path,
    findings: list[Finding],
) -> tuple[bool, list[str]]:
    after = snapshot_path(target)
    diff = diff_snapshots(baseline, after)
    passed = not diff
    if not passed:
        findings.append(Finding(
            profile="integrity-guard",
            scenario="zero_trace_verification",
            status="CATASTROPHIC",
            severity="critical",
            summary="Original target changed during Chaos Pass.",
            evidence=diff,
            suspected_cause="A tool, adapter, target process, or external process modified the original target.",
            recommended_action="Restore from a trusted snapshot and fix the offending adapter before another destructive run.",
            adapter="integrity-guard",
        ))
    return passed, diff

def run(
    target: Path,
    profile: str,
    max_clone_bytes: int,
    seed: int | None = None,
    *,
    config_path: Path | None = None,
    evidence_root: Path | None = None,
) -> RunReport:
    target = target.resolve()
    started = _utc()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    baseline = snapshot_path(target)
    baseline_bytes = snapshot_size(baseline)
    chosen_seed = seed if seed is not None else random.SystemRandom().randrange(0, 2**31)

    config = load_target_config(target, config_path)
    fingerprint, adapters = discover_adapters(target, config)
    evidence_dir = (evidence_root.resolve() / f"{run_id}_evidence") if evidence_root else None
    if evidence_dir:
        evidence_dir.mkdir(parents=True, exist_ok=True)

    findings: list[Finding] = []
    notes = [
        f"wildcard_seed={chosen_seed}",
        "adapters=" + ",".join(adapters.names),
        "target_kinds=" + ",".join(adapters.target_kinds),
        "capabilities=" + ",".join(adapters.capabilities),
        f"config_source={config.source or '<none>'}",
    ]

    try:
        sandbox = clone_target(target, max_bytes=max_clone_bytes)
    except Exception as exc:
        findings.append(Finding(
            profile="preflight",
            scenario="sandbox_creation",
            status="BLOCKED",
            severity="high",
            summary=f"Chaos Pass refused to start destructive testing: {type(exc).__name__}: {exc}",
            recommended_action="Resolve the isolation problem or use a stronger disposable environment before retrying.",
            adapter="safety",
        ))
        integrity_passed, integrity_diff = _integrity_result(baseline, target, findings)
        return RunReport(
            run_id=run_id,
            target=str(target),
            profile=profile,
            started_utc=started,
            finished_utc=_utc(),
            baseline_files=len(baseline),
            baseline_bytes=baseline_bytes,
            integrity_passed=integrity_passed,
            integrity_diff=integrity_diff,
            findings=findings,
            adapter_names=adapters.names,
            target_kinds=adapters.target_kinds,
            adapter_capabilities=adapters.capabilities,
            evidence_path=str(evidence_dir or ""),
            notes=notes,
        )

    try:
        process_root = sandbox.path if sandbox.path.is_dir() else sandbox.path.parent
        allow_network = config.chaos.get("allow_network", False) is True
        process_runner = SandboxProcessRunner(
            process_root,
            evidence_dir=evidence_dir,
            allow_network=allow_network,
        )
        notes.append(f"process_network={'allow' if allow_network else 'deny-best-effort'}")

        for phase_name in _phase_names(profile):
            definition = load_profile_definition(phase_name)
            plan = adapters.plan(definition)
            notes.append(
                f"plan:{phase_name}:actions={len(plan.actions)}:uncovered={len(plan.uncovered_surfaces)}"
            )
            if evidence_dir:
                plan_path = evidence_dir / f"plan-{phase_name}.json"
                plan_path.write_text(
                    json.dumps(plan.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                notes.append(f"plan_file:{phase_name}={plan_path}")
            context = AdapterContext(
                original_target=target,
                sandbox_target=sandbox.path,
                run_id=run_id,
                profile=phase_name,
                profile_definition=definition,
                fingerprint=fingerprint,
                config=config,
                process_runner=process_runner,
                metadata={
                    "adapter_names": ",".join(adapters.names),
                    "target_kinds": ",".join(adapters.target_kinds),
                },
            )
            for scenario in definition["scenarios"]:
                scenario_name = str(scenario)
                if scenario_name.startswith("adapter:"):
                    findings.extend(adapters.run_scenario(scenario_name, context))
                else:
                    generic = run_scenario(sandbox.path, phase_name, scenario_name, chosen_seed)
                    for finding in generic:
                        if not finding.adapter:
                            finding.adapter = "generic-core"
                    findings.extend(generic)
    finally:
        sandbox.cleanup()

    integrity_passed, integrity_diff = _integrity_result(baseline, target, findings)
    return RunReport(
        run_id=run_id,
        target=str(target),
        profile=profile,
        started_utc=started,
        finished_utc=_utc(),
        baseline_files=len(baseline),
        baseline_bytes=baseline_bytes,
        integrity_passed=integrity_passed,
        integrity_diff=integrity_diff,
        findings=findings,
        adapter_names=adapters.names,
        target_kinds=adapters.target_kinds,
        adapter_capabilities=adapters.capabilities,
        evidence_path=str(evidence_dir or ""),
        notes=notes,
    )