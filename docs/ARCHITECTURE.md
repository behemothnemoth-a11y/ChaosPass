# Architecture

Chaos Pass separates **how to break things** from **what is being tested**.

## Core

The core owns baseline manifests, disposable cloning, scenario orchestration, evidence, reports, teardown, and zero-trace verification.

## Profiles

Profiles describe testing behavior. They are reusable across targets and should not contain production-specific assumptions.

## Adapters

Adapters teach Chaos Pass how a specific target class behaves: desktop app, game, website, CLI, API, Minecraft mod/world, repository, filesystem workflow, database-backed service, or another authorized environment.

An adapter may provide:
- expert roles and golden paths;
- safe launch/stop/reset operations;
- target-specific scenarios;
- performance metrics;
- UI automation hooks;
- persistence/reload probes;
- evidence capture;
- target-specific restoration checks.

If a destructive probe cannot be guaranteed isolated, the adapter must return BLOCKED rather than guessing.

## Full-pass lifecycle

Expert Baseline -> Power User -> targeted chaos personas -> Random Chaos -> Wildcard -> Charlie -> Soak/Regression -> Final Boss -> teardown -> original integrity verification -> report.
