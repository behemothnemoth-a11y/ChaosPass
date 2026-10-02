# Architecture

Chaos Pass separates **how to break things** from **what is being tested**.

## Core

The core owns:

- pre-run baseline manifests;
- disposable cloning;
- link/junction isolation checks;
- profile orchestration;
- adapter discovery;
- generic scenarios;
- process evidence;
- teardown;
- post-run original-target verification;
- Markdown + JSON reporting.

## Profiles

Profiles describe tester behavior, not target implementation.

A profile defines:

- mission and mindset;
- priority attack surfaces;
- opening moves;
- escalation ladder;
- signature tactics;
- combination rules;
- handoff triggers;
- stop conditions;
- required evidence;
- portable scenario IDs.

The same Wildcard or Charlie profile can be applied to a CLI, game, website, desktop tool, or data workflow. The adapter layer decides how that intent maps to safe concrete actions.

## Target fingerprint

Before destructive testing, Chaos Pass performs read-only target classification:

- filesystem;
- Git repository;
- Python project;
- Node project;
- Rust project;
- opaque executable;
- configured CLI;
- additional future target kinds.

Fingerprinting records sampled file/size/extension information and marker files. It does not launch the target.

## Adapter registry

Multiple adapters may apply at once.

Example:

```text
Python Git repository
    ├── filesystem adapter
    ├── git-repository adapter
    ├── python-project adapter
    └── playbook-driver adapter
```

Each adapter advertises capabilities and the `adapter:*` scenario IDs it can execute.

## Plans

`chaos-pass plan` combines the selected persona with target adapters.

Plans distinguish:

- **auto actions** — the framework can execute them inside the disposable environment;
- **driver actions** — an external authorized UI/computer driver is required.

A driver action is not counted as tested until a real driver performs it and returns evidence.

## Process runner

All automatic target-process probes go through `SandboxProcessRunner`.

It enforces:

- cwd inside the disposable target;
- no shell execution;
- absolute non-command arguments may not escape the sandbox;
- disposable HOME/AppData/temp/config/cache/package-manager state;
- stripping inherited secrets/tokens/passwords/API keys/credential variables;
- best-effort network denial by default;
- process-group/process-tree cleanup on timeout;
- stdout/stderr/process metadata capture.

## Built-in adapters

### Filesystem

Universal base adapter. Provides target recon, hash/readability checks, timing, and clone-only identity/move/rename probes.

### Git repository

Read-only Git object/connectivity/index probes using the cloned working tree.

### Minecraft world

Detects saves from `level.dat` plus normal world directories. Performs dependency-free NBT parsing, region allocation checks, datapack integrity/state/collision analysis, SQLite/JSON validation, static persistence checks, and emits Minecraft-specific live-driver actions for UI/save/reload/performance work.

### Python project

Parses `pyproject.toml` and uses `compileall` to check source syntax without importing/executing project code.

### Node project

Parses `package.json` and, when Node is available, uses bounded `node --check` syntax probes. It never automatically runs npm scripts.

### Rust project

Parses `Cargo.toml`. It intentionally does not run Cargo build scripts automatically.

### Opaque executable

Recognizes executable-file targets but does not launch them automatically.

### Configured CLI

Runs only probes explicitly declared in `chaospass.toml` with `allow_process_execution = true`.

### Playbook driver

Converts persona opening moves and signature tactics into structured external-driver tasks for GUI/application-specific execution.

## Configuration

`chaospass.toml` is optional and read-only from Chaos Pass's perspective. The framework never creates or edits target configuration during a run.

Configured probes are the target owner's explicit declaration that a command is appropriate to execute against a disposable clone and what result counts as healthy.

## Full-pass lifecycle

```text
Read-only inspect
    ↓
Baseline original
    ↓
Select adapters + build plans
    ↓
Clone / sandbox
    ↓
Expert Baseline
    ↓
Power User
    ↓
Targeted personas
    ↓
Random Chaos
    ↓
Wildcard
    ↓
Soak / Regression
    ↓
Final Boss
    ↓
Recovery
    ↓
Destroy disposable state
    ↓
Verify original == baseline
    ↓
Full report + evidence
```

If safe isolation cannot be established, the destructive portion is **BLOCKED** and the framework still returns a report plus an original-integrity result.