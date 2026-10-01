# Chaos Pass

> **Try to break anything. Restore everything. Document everything.**

Chaos Pass is a general-purpose adversarial QA and stress-testing framework for authorized targets. It starts with conventional expert review, escalates through power-user and chaos profiles, combines weak points, then proves the original target was left unchanged.

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
- **Targeted Chaos Profiles** — boundary, misuse, scale, persistence, state, UI, Charlie, and more.
- **Random Chaos** — reproducible seeded unpredictability.
- **Wildcard** — adapts mid-run and changes strategy based on what just bent or broke.
- **Final Boss** — combine weak points and overlapping stressors.
- **Recovery + Integrity** — destroy the sandbox and verify the original.
- **Full Report** — findings, reproduction, evidence, suspected causes, fixes, and integrity result.

## Included profiles

Expert Baseline · Power User · Chaos Goblin · Boundary Hunter · Wrong-Way User · UI Gremlin · Performance Murderer · Persistence Demon · State Breaker · Charlie · Random Chaos · Wildcard · Soak Monster · Regression Archaeologist · Full Chaos Pass.

**Random Chaos** uses a recorded seed to choose a fixed unpredictable sequence that can be reproduced later.

**Wildcard** is different: it observes earlier outcomes and changes its next move to pursue whatever looks weakest.

**Charlie** models catastrophically unconventional problem solving: odd interpretations, improvised workflows, wrong-tool-right-now choices, circular workarounds, path/naming chaos, and “fixes” that create larger downstream problems. It is a testing philosophy inspired by that style of fictional chaos, not an impersonation.

## Result vocabulary

- **SURVIVED** — tested and held up.
- **BEND** — works, but degrades or behaves poorly.
- **WEIRD** — unexpected behavior worth investigating.
- **BREAK** — functionality failed.
- **CATASTROPHIC** — crash, corruption, unrecoverable sandbox state, or a zero-trace framework failure.
- **BLOCKED** — interesting test could not be safely or generically executed.

## Quick start

Requires Python 3.11+.

```powershell
cd C:\Users\behem\Documents\Chaos-Pass
python -m chaos_pass run --target "C:\path\to\authorized\target" --profile full-chaos-pass
```

Reports are written outside the target by default. DROP 0001 includes generic filesystem-safe probes and intentionally marks application-specific checks as **BLOCKED** until a proper adapter exists rather than touching live state blindly.

## Safety boundary

Chaos Pass is for systems you own or are explicitly authorized to test. Never use the framework to hammer third-party production infrastructure, real customer data, billing systems, live email delivery, or other irreversible external actions. Use test doubles, sandboxes, fixtures, staging, or disposable copies.

## Inspiration

Chaos Pass borrows the spirit of chaotic experimentation, limit-pushing, and unconventional-user testing seen in entertainment and software break-testing culture. It is not affiliated with Let's Game It Out, *It's Always Sunny in Philadelphia*, or their creators.

## Status

**DROP 0001 — Foundation / Major Drop**

This establishes the zero-trace contract, expert-first lifecycle, profile system, generic sandbox runner, report format, adapter interface, deterministic regression seeds, and regression-ready architecture.
