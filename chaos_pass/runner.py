from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import random
import uuid

from .models import Finding, RunReport
from .profiles import load_profile
from .safety import clone_target, diff_snapshots, snapshot_path, snapshot_size
from .scenarios import run_scenario

def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()

def _phase_plan(profile: str) -> list[tuple[str, list[str]]]:
    if profile != "full-chaos-pass":
        return [(profile, load_profile(profile))]

    order = [
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
    return [(name, load_profile(name)) for name in order]

def run(
    target: Path,
    profile: str,
    max_clone_bytes: int,
    seed: int | None = None,
) -> RunReport:
    target = target.resolve()
    started = _utc()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    baseline = snapshot_path(target)
    baseline_bytes = snapshot_size(baseline)
    chosen_seed = seed if seed is not None else random.SystemRandom().randrange(0, 2**31)
    findings: list[Finding] = []
    notes = [f"wildcard_seed={chosen_seed}"]

    sandbox = clone_target(target, max_bytes=max_clone_bytes)
    try:
        for phase_name, scenarios in _phase_plan(profile):
            for scenario in scenarios:
                findings.extend(run_scenario(sandbox.path, phase_name, scenario, chosen_seed))
    finally:
        sandbox.cleanup()

    after = snapshot_path(target)
    integrity_diff = diff_snapshots(baseline, after)
    integrity_passed = not integrity_diff
    if not integrity_passed:
        findings.append(Finding(
            profile="integrity-guard",
            scenario="zero_trace_verification",
            status="CATASTROPHIC",
            severity="critical",
            summary="Original target changed during Chaos Pass.",
            evidence=integrity_diff,
            suspected_cause="A tool, adapter, or external process modified the original target.",
            recommended_action="Treat this as a framework failure. Restore from a trusted snapshot and fix the offending adapter before another run.",
        ))

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
        notes=notes,
    )
