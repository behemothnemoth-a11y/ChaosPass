# Target Configuration — chaospass.toml

A target can opt into executable CLI probes by adding `chaospass.toml` or `.chaospass.toml` at its root, or by passing `--config <path>`.

Nothing writes this file automatically.

## Minimal configured CLI

```toml
[chaospass]
allow_process_execution = true
allow_network = false

[cli]
command = ["python", "app.py"]
timeout_seconds = 5

[[cli.probes]]
id = "help"
scenario = "adapter:expert-domain"
args = ["--help"]
expected_exit_codes = [0]
stdout_contains = "usage"
```

`allow_process_execution` is required. Without it, the configured CLI adapter will not launch the program.

`allow_network` defaults to false. When false, Chaos Pass uses credential stripping plus dead proxy variables as best-effort network suppression. This is not equivalent to VM/container firewall isolation.

## Probe fields

- `id`: stable evidence/reproduction label.
- `scenario`: persona adapter scenario, for example `adapter:expert-domain`, `adapter:expert-qa`, `adapter:wrong_way`, `adapter:persistence`, `adapter:state`, `adapter:charlie`, or `adapter:regression`.
- `args`: arguments appended to the configured command.
- `expected_exit_codes`: accepted exit codes, default `[0]`.
- `stdout_contains`: optional required substring.
- `stderr_contains`: optional required substring.
- `timeout_seconds`: per-probe timeout override.
- `repeat`: repeat count, hard-capped at 20.
- `cwd`: relative working directory inside the cloned target.

## Important path rule

The first command element may resolve from PATH or be an interpreter executable. File arguments should remain relative to the cloned target. Absolute non-command arguments that escape the sandbox are rejected.

## Expected failures

Wrong-Way User probes can intentionally expect a non-zero exit code:

```toml
[[cli.probes]]
id = "invalid-option"
scenario = "adapter:wrong_way"
args = ["--definitely-invalid"]
expected_exit_codes = [2]
stderr_contains = "unknown"
```

A correctly rejected invalid request is then reported as SURVIVED rather than BREAK.

## Why explicit probes matter

Chaos Pass cannot infer that `npm test`, `pytest`, `gradle test`, a game launcher, or a production CLI is side-effect free. Explicit probes let the target owner state which commands are appropriate inside the disposable clone and what outcome counts as healthy.