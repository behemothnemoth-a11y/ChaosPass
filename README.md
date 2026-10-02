# Chaos Pass

> **Try to break anything. Restore everything. Document everything.**

Chaos Pass is a general-purpose adversarial QA and stress-testing framework for authorized targets. It starts with conventional expert review, then escalates through power-user and chaos profiles designed to expose weak assumptions, bad states, performance cliffs, persistence failures, and bizarre interactions.

The original/live target is **never** the punching bag. Mutating tests run only against a disposable clone, sandbox, snapshot, test world, VM, container, or equivalent. A run is not complete until the original target is verified against its pre-run baseline.

## Core contract

1. **Baseline first.** Record the original target before testing.
2. **Clone before mutation.** Destructive work happens only in isolation.
3. **Break aggressively.** Push limits, misuse workflows, combine weak points.
4. **Collect evidence.** Every meaningful result gets reproducible notes.
5. **Tear down the damage.** Disposable test state is removed.
6. **Verify zero trace.** The original must match its baseline.
7. **Report everything.** Survived, bent, weird, broken, catastrophic, or blocked.

## Pass order

- **Expert Baseline** — domain expert, QA, UX, accessibility, performance/reliability, and security/safety where applicable.
- **Power User** — fast, competent, advanced but still valid use.
- **Chaos Profiles** — targeted adversarial behavior.
- **Final Boss** — combine the weak points discovered earlier.
- **Recovery + Integrity** — destroy the sandbox and verify the original.
- **Full Report** — findings, reproduction, evidence, suspected causes, fixes, and integrity result.

## Included profiles

Expert Baseline · Power User · Chaos Goblin · Boundary Hunter · Wrong-Way User · UI Gremlin · Performance Murderer · Persistence Demon · State Breaker · Charlie · Random Chaos · Wildcard · Soak Monster · Regression Archaeologist · Full Chaos Pass.

**Wildcard** adapts mid-run and chases whatever looks breakable instead of following a fixed script.

**Charlie** models catastrophically unconventional problem solving: odd interpretations, improvised workflows, wrong-tool-right-now choices, circular workarounds, path/naming chaos, and “fixes” that create larger downstream problems. It is a testing philosophy inspired by that style of fictional chaos, not an impersonation.

## Result vocabulary

- **SURVIVED** — tested and held up.
- **BEND** — works, but degrades or behaves poorly.
- **WEIRD** — unexpected behavior worth investigating.
- **BREAK** — functionality failed.
- **CATASTROPHIC** — crash, corruption, or unrecoverable sandbox state.
- **BLOCKED** — interesting test could not be safely or generically executed.

## Quick start

Requires Python 3.11+.

```powershell
cd C:\Users\behem\Documents\Chaos-Pass

# Read-only target fingerprint + adapter detection
python -m chaos_pass inspect-target --target "C:\path\to\authorized\target"

# See what Wildcard can automate and what needs an external driver
python -m chaos_pass plan --target "C:\path\to\authorized\target" --profile wildcard

# Run the full expert -> chaos -> recovery pipeline
python -m chaos_pass run --target "C:\path\to\authorized\target" --profile full-chaos-pass
```

Reports and process evidence are written outside the target. Built-in adapters recognize filesystem targets, Git repositories, Python projects, Node projects, Rust projects, opaque executables, and explicitly configured CLI programs. Unsupported GUI behavior becomes a structured external-driver task rather than being silently treated as tested.

## Safety boundary

Chaos Pass is for systems you own or are explicitly authorized to test. Never use the framework to hammer third-party production infrastructure, real customer data, billing systems, live email delivery, or other irreversible external actions. Use test doubles, sandboxes, fixtures, staging, or disposable copies.

## Inspiration

Chaos Pass borrows the spirit of chaotic experimentation, limit-pushing, and unconventional-user testing seen in entertainment and software break-testing culture. It is not affiliated with Let's Game It Out, *It's Always Sunny in Philadelphia*, or their creators.

## Persona playbooks

Every profile now defines how it should attack an unfamiliar program: mission, mindset, priority surfaces, opening moves, escalation ladder, signature tactics, combination rules, handoff triggers, stop conditions, and required evidence.

Inspect any playbook directly:

```powershell
python -m chaos_pass describe-profile wildcard
python -m chaos_pass describe-profile charlie
```

See `docs/PROGRAM_ATTACK_MODEL.md`, `docs/PROFILE_SCHEMA.md`, and `docs/PROFILE_CATALOG.md`.

## Adapter engine

DROP 0003 maps persona intent onto target-aware adapters. Safe static/read-only probes can execute automatically in the disposable clone. Program-specific commands require explicit `chaospass.toml` opt-in. GUI/opaque actions are emitted as external-driver tasks.

See `docs/ADAPTER_ENGINE.md`, `docs/TARGET_CONFIG.md`, and `docs/DRIVER_PROTOCOL.md`.

## Minecraft worlds

Minecraft saves are first-class targets. The Minecraft adapter recognizes worlds from `level.dat`, validates NBT/regions/datapacks/mod-side SQLite/JSON state, detects duplicate enabled datapacks and function-path collisions, and emits live Minecraft driver tasks for save/reload/UI/performance testing.

```powershell
python -m chaos_pass inspect-target --target "C:\path\to\.minecraft\saves\World"
python -m chaos_pass run --target "C:\path\to\.minecraft\saves\World" --profile full-chaos-pass
```

See `docs/MINECRAFT_ADAPTER.md`.

## Regression corpus

Historical findings can live under `regressions/*.json`. Regression Archaeologist loads them into its plan and report so bugs discovered by earlier Chaos Pass runs stay part of future testing.

```powershell
python -m chaos_pass list-regressions --target .
python -m chaos_pass plan --target . --profile regression-archaeologist
```

See `docs/REGRESSION_CORPUS.md`.

## Status

**DROP 0005 — Minecraft World Adapter**

DROP 0005 makes Minecraft worlds first-class Chaos Pass targets with static world validation, datapack/state analysis, duplicate/collision detection, Minecraft-specific persona behavior, and live-driver plans while preserving the zero-trace rule.