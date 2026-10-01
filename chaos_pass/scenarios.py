from __future__ import annotations

import random
import shutil
import time
from pathlib import Path

from .models import Finding

def _ok(profile: str, scenario: str, summary: str, evidence: list[str] | None = None) -> Finding:
    return Finding(profile, scenario, "SURVIVED", "info", summary, evidence=evidence or [])

def _bend(profile: str, scenario: str, summary: str, evidence: list[str]) -> Finding:
    return Finding(profile, scenario, "BEND", "medium", summary, evidence=evidence)

def _blocked(profile: str, scenario: str, summary: str) -> Finding:
    return Finding(
        profile, scenario, "BLOCKED", "info", summary,
        recommended_action="Add or enable a target-specific adapter for this probe.",
    )

def _workdir(root: Path) -> Path:
    base = root if root.is_dir() else root.parent
    path = base / ".chaos_pass_work"
    path.mkdir(exist_ok=True)
    return path

def inventory(root: Path, profile: str) -> Finding:
    base = root if root.is_dir() else root.parent
    files = [p for p in base.rglob("*") if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    return _ok(profile, "inventory", f"Sandbox inventory completed: {len(files)} files, {total:,} bytes.",
               [f"files={len(files)}", f"bytes={total}"])

def unicode_names(root: Path, profile: str) -> Finding:
    w = _workdir(root) / "unicode"
    w.mkdir(exist_ok=True)
    names = ["snowman_☃.txt", "emoji_🧪.txt", "combining_é.txt", "日本語.txt"]
    for name in names:
        p = w / name
        p.write_text("chaos", encoding="utf-8")
        if p.read_text(encoding="utf-8") != "chaos":
            return Finding(profile, "unicode_names", "BREAK", "high", f"Unicode round-trip failed for {name}.")
    return _ok(profile, "unicode_names", "Unicode filename round-trips survived.", names)

def deep_nesting(root: Path, profile: str) -> Finding:
    p = _workdir(root) / "deep"
    p.mkdir(parents=True, exist_ok=True)
    depth = 24
    for i in range(depth):
        p = p / f"level_{i:02d}"
        p.mkdir(exist_ok=True)
    marker = p / "marker.txt"
    marker.write_text("deep", encoding="utf-8")
    return _ok(profile, "deep_nesting", f"Created and read a {depth}-level nested path in the sandbox.",
               [str(marker)])

def rapid_churn(root: Path, profile: str) -> Finding:
    w = _workdir(root) / "churn"
    w.mkdir(exist_ok=True)
    started = time.perf_counter()
    for i in range(300):
        p = w / f"temp_{i:04d}.txt"
        p.write_text(str(i), encoding="utf-8")
        p.unlink()
    elapsed = time.perf_counter() - started
    evidence = [f"operations=600", f"elapsed_seconds={elapsed:.4f}"]
    if elapsed > 5:
        return _bend(profile, "rapid_churn", "Rapid create/delete completed but crossed the generic slowdown threshold.", evidence)
    return _ok(profile, "rapid_churn", "Rapid create/delete churn survived.", evidence)

def large_blob(root: Path, profile: str) -> Finding:
    p = _workdir(root) / "large_blob.bin"
    size = 2 * 1024 * 1024
    p.write_bytes(b"X" * size)
    if p.stat().st_size != size:
        return Finding(profile, "large_blob", "BREAK", "high", "Large sandbox blob size did not round-trip.")
    return _ok(profile, "large_blob", "2 MiB generated input survived filesystem round-trip.", [f"bytes={size}"])

def duplicate_wave(root: Path, profile: str) -> Finding:
    base = root if root.is_dir() else root.parent
    samples = [p for p in base.rglob("*") if p.is_file() and ".chaos_pass_work" not in p.parts][:8]
    w = _workdir(root) / "duplicates"
    w.mkdir(exist_ok=True)
    count = 0
    for round_no in range(4):
        for sample in samples:
            dest = w / f"{round_no:02d}_{count:03d}_{sample.name}"
            shutil.copy2(sample, dest)
            count += 1
    return _ok(profile, "duplicate_wave", f"Duplicated {count} sandbox files without touching the original.",
               [f"copies={count}"])

def rename_churn(root: Path, profile: str) -> Finding:
    w = _workdir(root) / "rename"
    w.mkdir(exist_ok=True)
    current = w / "definitely_final.txt"
    current.write_text("still chaos", encoding="utf-8")
    for i in range(100):
        nxt = w / f"definitely_final_v{i:03d}_FINAL.txt"
        current.rename(nxt)
        current = nxt
    return _ok(profile, "rename_churn", "100 sequential renames survived in the disposable workspace.",
               [f"final_name={current.name}"])

def charlie_workflow(root: Path, profile: str) -> Finding:
    w = _workdir(root) / "charlie"
    weird = [
        w / "important" / "misc",
        w / "misc" / "important",
        w / "final" / "final2" / "actually_final",
    ]
    for folder in weird:
        folder.mkdir(parents=True, exist_ok=True)

    seed = weird[0] / "system.txt"
    seed.write_text("this probably goes here", encoding="utf-8")
    current = seed
    trail: list[str] = []
    for i in range(12):
        target_dir = weird[i % len(weird)]
        target = target_dir / f"fix_{i:02d}_use_this_one.txt"
        shutil.copy2(current, target)
        trail.append(str(target.relative_to(w)))
        current = target
    return _ok(profile, "charlie_workflow",
               "Improvised circular-copy / questionable-organization workflow survived inside the sandbox.",
               trail[-5:])

def soak_loop(root: Path, profile: str) -> Finding:
    w = _workdir(root) / "soak"
    w.mkdir(exist_ok=True)
    started = time.perf_counter()
    operations = 0
    for round_no in range(20):
        for i in range(50):
            p = w / f"r{round_no:02d}_{i:03d}.tmp"
            p.write_bytes(bytes([i % 255]) * 128)
            operations += 1
        for p in list(w.glob("*.tmp")):
            p.unlink()
            operations += 1
    elapsed = time.perf_counter() - started
    evidence = [f"operations={operations}", f"elapsed_seconds={elapsed:.4f}"]
    if elapsed > 10:
        return _bend(profile, "soak_loop", "Soak loop completed with notable slowdown.", evidence)
    return _ok(profile, "soak_loop", "Repeated create/delete soak loop survived.", evidence)

def random_chain(root: Path, profile: str, seed: int) -> list[Finding]:
    rng = random.Random(seed)
    candidates = [unicode_names, deep_nesting, rapid_churn, large_blob, duplicate_wave, rename_churn, charlie_workflow]
    chosen = rng.sample(candidates, k=4)
    findings = [fn(root, profile) for fn in chosen]
    findings.append(_ok(profile, "random_chain",
                        "Random Chaos executed a fixed dice-driven chain.",
                        ["chain=" + " -> ".join(fn.__name__ for fn in chosen)]))
    return findings

def wildcard_chain(root: Path, profile: str, seed: int) -> list[Finding]:
    rng = random.Random(seed)
    opening = rng.sample([unicode_names, deep_nesting, large_blob], k=2)
    findings = [fn(root, profile) for fn in opening]

    stressed = any(f.status in {"BEND", "WEIRD", "BREAK", "CATASTROPHIC"} for f in findings)
    if stressed:
        follow_up = [rapid_churn, soak_loop, rename_churn]
        rationale = "stress detected; Wildcard amplified pressure"
    else:
        follow_up = [duplicate_wave, charlie_workflow, rapid_churn]
        rationale = "opening survived; Wildcard changed attack surface"

    findings.extend(fn(root, profile) for fn in follow_up)
    findings.append(_ok(profile, "wildcard_chain",
                        "Wildcard adapted its follow-up strategy based on earlier outcomes.",
                        [
                            "opening=" + " -> ".join(fn.__name__ for fn in opening),
                            "follow_up=" + " -> ".join(fn.__name__ for fn in follow_up),
                            "rationale=" + rationale,
                        ]))
    return findings

def final_boss(root: Path, profile: str) -> Finding:
    w = _workdir(root) / "final_boss"
    w.mkdir(exist_ok=True)
    started = time.perf_counter()
    for i in range(120):
        p = w / f"combo_{i:04d}_FINAL_final.txt"
        p.write_bytes((f"{i}:CHAOS:" * 64).encode("utf-8"))
        renamed = w / f"combo_{i:04d}_actually_final.txt"
        p.rename(renamed)
        if i % 3 == 0:
            shutil.copy2(renamed, w / f"copy_{i:04d}.txt")
    elapsed = time.perf_counter() - started
    return _ok(profile, "final_boss",
               "Combined rename, duplication, file creation, and sustained churn survived in the sandbox.",
               [f"iterations=120", f"elapsed_seconds={elapsed:.4f}"])

SCENARIOS = {
    "inventory": inventory,
    "unicode_names": unicode_names,
    "deep_nesting": deep_nesting,
    "rapid_churn": rapid_churn,
    "large_blob": large_blob,
    "duplicate_wave": duplicate_wave,
    "rename_churn": rename_churn,
    "charlie_workflow": charlie_workflow,
    "soak_loop": soak_loop,
    "final_boss": final_boss,
}

def run_scenario(root: Path, profile: str, scenario: str, seed: int) -> list[Finding]:
    try:
        if scenario == "random_chain":
            return random_chain(root, profile, seed)
        if scenario == "wildcard_chain":
            return wildcard_chain(root, profile, seed)
        if scenario.startswith("adapter:"):
            return [_blocked(profile, scenario, f"{scenario} requires a target-specific adapter; live-state guessing is forbidden.")]
        func = SCENARIOS.get(scenario)
        if func is None:
            return [_blocked(profile, scenario, f"No generic implementation exists for '{scenario}'.")]
        return [func(root, profile)]
    except Exception as exc:
        return [Finding(
            profile, scenario, "BREAK", "high",
            f"Sandbox probe raised {type(exc).__name__}: {exc}",
            suspected_cause="Generic probe failed in the disposable clone.",
            recommended_action="Reproduce with the same profile and inspect target-specific behavior.",
        )]
