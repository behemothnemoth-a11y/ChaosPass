# Adapter Engine

DROP 0003 connects persona intent to target-specific actions.

## Flow

1. `inspect-target` fingerprints the target read-only.
2. The registry selects every compatible adapter.
3. `plan` merges automatic adapter actions with external-driver actions derived from the selected persona.
4. `run` creates a disposable clone.
5. Generic scenarios run only in that clone.
6. `adapter:*` scenarios are dispatched to compatible target adapters.
7. Process probes run with redirected user/config/cache/temp state and a sanitized environment.
8. Evidence is saved outside the target.
9. The clone is destroyed.
10. The original is resnapshotted and must match its baseline.

## Built-in adapters

| Adapter | Detects | Automatic behavior |
| --- | --- | --- |
| filesystem | any file/directory | recon, full hash/readability baseline, snapshot timing, sandbox-only identity probes |
| git-repository | `.git` | HEAD/tracked-file recon, connectivity/object integrity, index timing |
| minecraft-world | `level.dat` plus normal world directories | NBT, region, datapack, SQLite/JSON, persistence/state static checks plus Minecraft-specific driver plans |
| python-project | `pyproject.toml`, `setup.py`, or `requirements.txt` | manifest recon and `compileall` without importing project code |
| node-project | `package.json` | package manifest recon and bounded `node --check` syntax probes when Node exists |
| rust-project | `Cargo.toml` | Cargo manifest recon without running build scripts |
| opaque-executable | executable file target | detection only; launch requires explicit configuration |
| configured-cli | `chaospass.toml` CLI probe config | explicit commands, exit-code assertions, output assertions, repeats, timeouts |
| playbook-driver | every target | translates persona opening moves/signature tactics into non-executable driver tasks |

Adapters stack. A Python Git repository can receive filesystem + Git + Python coverage in the same pass.

## Why tests are not auto-run by default

Project test commands are code execution. They may contact networks, mutate databases, send messages, or depend on real credentials. Chaos Pass therefore auto-runs only bounded static/read-only probes that are understood by the adapter. Project-specific executable probes must be explicitly declared in `chaospass.toml`.

## Process sandbox hardening

Configured/adapter processes:

- run with cwd inside the disposable target;
- receive disposable HOME/USERPROFILE/APPDATA/LOCALAPPDATA/TEMP directories;
- receive disposable Cargo/npm/pip/Gradle/.NET/NuGet homes/caches;
- do not inherit environment variables whose names look like tokens, passwords, secrets, API keys, credentials, or private/access keys;
- do not inherit SSH_AUTH_SOCK or common credential-path variables;
- default HTTP(S)/ALL proxy variables to a dead localhost endpoint;
- run in a new process group and receive process-tree termination on timeout;
- persist stdout/stderr/process metadata to the report evidence folder.

The proxy policy is **best-effort**, not a network namespace or firewall. Use a VM/container/test environment when hard network isolation is required.

## Link/reparse safety

Snapshots do not recurse through symlinks or Windows junctions. A target containing a link/junction that escapes the target tree is refused before destructive testing. The cloned tree is checked again before execution.

## Adapter scenarios

Profiles still use portable scenario IDs such as `adapter:expert-domain`, `adapter:wrong_way`, or `adapter:persistence`. Each adapter decides whether it can safely turn that intent into a concrete test. Unsupported intent remains BLOCKED and is also available as an external-driver task through the plan.