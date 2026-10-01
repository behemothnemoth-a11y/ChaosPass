from __future__ import annotations

from pathlib import Path
import json
import os
import shutil
import sys
import time
import tomllib
from typing import Any

from .adapters import AdapterAction, AdapterContext, BaseAdapter, TargetFingerprint
from .config import TargetConfig
from .models import Finding
from .safety import snapshot_path

def _finding(
    context: AdapterContext,
    scenario: str,
    status: str,
    summary: str,
    *,
    severity: str = "info",
    evidence: list[str] | None = None,
    reproduction: list[str] | None = None,
    cause: str = "",
    action: str = "",
) -> Finding:
    return Finding(
        profile=context.profile,
        scenario=scenario,
        status=status,
        severity=severity,
        summary=summary,
        evidence=evidence or [],
        reproduction=reproduction or [],
        suspected_cause=cause,
        recommended_action=action,
    )

def _process_finding(
    context: AdapterContext,
    scenario: str,
    label: str,
    argv: list[str],
    *,
    expected_exit_codes: set[int] | None = None,
    timeout_seconds: float = 10.0,
    cwd: Path | None = None,
    success_summary: str,
) -> Finding:
    expected = expected_exit_codes or {0}
    result = context.process_runner.run(
        argv,
        label=label,
        cwd=cwd or context.sandbox_target,
        timeout_seconds=timeout_seconds,
    )
    evidence = [
        "argv=" + " ".join(result.argv),
        f"exit_code={result.exit_code}",
        f"elapsed_seconds={result.elapsed_seconds:.4f}",
        f"timed_out={result.timed_out}",
        *result.evidence_files,
    ]
    if result.timed_out:
        return _finding(
            context, scenario, "BEND",
            f"{label} exceeded the {timeout_seconds:g}s adapter timeout.",
            severity="medium", evidence=evidence,
            cause="The sandbox process did not complete inside the configured probe window.",
            action="Inspect the process evidence and characterize whether this is expected workload or a hang.",
        )
    if result.exit_code not in expected:
        return _finding(
            context, scenario, "BREAK",
            f"{label} exited with {result.exit_code}; expected {sorted(expected)}.",
            severity="high", evidence=evidence,
            cause="The target-specific probe returned an unexpected process result.",
            action="Inspect captured stdout/stderr and reproduce with the same sandbox probe.",
        )
    return _finding(context, scenario, "SURVIVED", success_summary, evidence=evidence)

class GenericFilesystemAdapter(BaseAdapter):
    name = "filesystem"
    target_kind = "filesystem"
    priority = 10
    capabilities = (
        "filesystem-recon",
        "filesystem-readability",
        "filesystem-timing",
        "sandbox-file-mutation",
        "identity-copy-probes",
    )
    scenarios = (
        "adapter:expert-domain",
        "adapter:expert-qa",
        "adapter:expert-performance-reliability",
        "adapter:wrong_way",
        "adapter:charlie",
    )

    def supports(self, fingerprint: TargetFingerprint, config: TargetConfig) -> bool:
        return True

    def plan(self, profile_definition: dict[str, Any]) -> list[AdapterAction]:
        actions = [
            AdapterAction("fs-recon", "Inventory file shapes, markers, and sampled size.", "filesystem-recon", "read-only", True, self.name),
        ]
        scenarios = set(profile_definition.get("scenarios", []))
        if "adapter:wrong_way" in scenarios:
            actions.append(AdapterAction("fs-wrong-way", "Move/rename a copied sample inside disposable work state.", "sandbox-file-mutation", "sandbox-mutation", True, self.name))
        if "adapter:charlie" in scenarios:
            actions.append(AdapterAction("fs-charlie", "Build confusing copied-resource identity chains inside the clone.", "identity-copy-probes", "sandbox-mutation", True, self.name))
        return actions

    def _sample_file(self, root: Path) -> Path | None:
        if root.is_file():
            return root
        for path in root.rglob("*"):
            if path.is_file() and ".chaos_pass_work" not in path.parts:
                return path
        return None

    def run_scenario(self, scenario: str, context: AdapterContext) -> list[Finding]:
        fp = context.fingerprint
        if scenario == "adapter:expert-domain":
            return [_finding(
                context, scenario, "SURVIVED",
                "Filesystem target recon completed.",
                evidence=[
                    f"path_kind={fp.path_kind}",
                    f"files_sampled={fp.file_count_sampled}",
                    f"bytes_sampled={fp.bytes_sampled}",
                    "markers=" + ",".join(fp.markers),
                    "extensions=" + ",".join(f"{k}:{v}" for k, v in fp.extension_counts.items()),
                    f"scan_truncated={fp.scan_truncated}",
                ],
            )]
        if scenario == "adapter:expert-qa":
            started = time.perf_counter()
            snap = snapshot_path(context.sandbox_target)
            elapsed = time.perf_counter() - started
            return [_finding(
                context, scenario, "SURVIVED",
                f"Sandbox filesystem baseline is readable and hashable ({len(snap)} entries).",
                evidence=[f"entries={len(snap)}", f"hash_seconds={elapsed:.4f}"],
            )]
        if scenario == "adapter:expert-performance-reliability":
            started = time.perf_counter()
            snap = snapshot_path(context.sandbox_target)
            elapsed = time.perf_counter() - started
            status = "BEND" if elapsed > 5 else "SURVIVED"
            severity = "medium" if status == "BEND" else "info"
            return [_finding(
                context, scenario, status,
                "Filesystem snapshot timing crossed the generic 5s baseline." if status == "BEND"
                else "Filesystem snapshot timing stayed under the generic 5s baseline.",
                severity=severity,
                evidence=[f"entries={len(snap)}", f"hash_seconds={elapsed:.4f}"],
            )]
        sample = self._sample_file(context.sandbox_target)
        work = (context.sandbox_target if context.sandbox_target.is_dir() else context.sandbox_target.parent) / ".chaos_pass_adapter_work"
        work.mkdir(parents=True, exist_ok=True)
        if sample is None:
            return [_finding(context, scenario, "BLOCKED", "No sample file exists for the filesystem identity probe.")]
        if scenario == "adapter:wrong_way":
            copied = work / "probably_goes_here.tmp"
            shutil.copy2(sample, copied)
            renamed = work / "actually_this_one.final"
            copied.rename(renamed)
            return [_finding(
                context, scenario, "SURVIVED",
                "Wrong-way copied-resource move/rename sequence stayed confined to the sandbox.",
                evidence=[f"sample={sample}", f"final_copy={renamed}"],
            )]
        if scenario == "adapter:charlie":
            current = work / "FINAL.txt"
            shutil.copy2(sample, current)
            trail = [current.name]
            for name in ("FINAL_2.txt", "ACTUALLY_FINAL.txt", "USE_THIS_ONE_FINAL.txt"):
                nxt = work / name
                shutil.copy2(current, nxt)
                current = nxt
                trail.append(name)
            return [_finding(
                context, scenario, "SURVIVED",
                "Charlie resource-copy identity chain completed inside disposable storage.",
                evidence=["trail=" + " -> ".join(trail)],
            )]
        return []

class GitRepositoryAdapter(BaseAdapter):
    name = "git-repository"
    target_kind = "git-repository"
    priority = 40
    capabilities = ("git-recon", "git-object-integrity", "git-diff-check", "sandbox-process")
    scenarios = (
        "adapter:expert-domain",
        "adapter:expert-qa",
        "adapter:expert-performance-reliability",
        "adapter:regression",
    )

    def supports(self, fingerprint: TargetFingerprint, config: TargetConfig) -> bool:
        return "git-repository" in fingerprint.target_kinds and shutil.which("git") is not None

    def plan(self, profile_definition: dict[str, Any]) -> list[AdapterAction]:
        return [
            AdapterAction("git-recon", "Inspect HEAD and tracked-file metadata without modifying repository state.", "git-recon", "read-only-process", True, self.name),
            AdapterAction("git-fsck", "Check Git object connectivity/integrity in the disposable repository copy.", "git-object-integrity", "read-only-process", True, self.name),
        ]

    def run_scenario(self, scenario: str, context: AdapterContext) -> list[Finding]:
        git = shutil.which("git") or "git"
        if scenario == "adapter:expert-domain":
            return [
                _process_finding(
                    context, scenario, "git-head",
                    [git, "rev-parse", "--verify", "HEAD"],
                    success_summary="Git HEAD resolves successfully in the sandbox copy.",
                ),
                _process_finding(
                    context, scenario, "git-ls-files",
                    [git, "ls-files"],
                    success_summary="Git tracked-file inventory completed.",
                ),
            ]
        if scenario == "adapter:expert-qa":
            return [_process_finding(
                context, scenario, "git-connectivity-check",
                [git, "fsck", "--connectivity-only", "--no-reflogs", "--no-progress"],
                timeout_seconds=20,
                success_summary="Git repository object connectivity check survived.",
            )]
        if scenario == "adapter:expert-performance-reliability":
            return [_process_finding(
                context, scenario, "git-index-enumeration",
                [git, "ls-files", "-z"],
                timeout_seconds=10,
                success_summary="Git index enumeration completed inside the performance probe window.",
            )]
        if scenario == "adapter:regression":
            return [_process_finding(
                context, scenario, "git-fsck",
                [git, "fsck", "--no-reflogs", "--no-progress"],
                timeout_seconds=20,
                success_summary="Git object integrity check survived.",
            )]
        return []

class PythonProjectAdapter(BaseAdapter):
    name = "python-project"
    target_kind = "python-project"
    priority = 60
    capabilities = (
        "python-manifest-recon",
        "python-static-compile",
        "python-compile-timing",
        "sandbox-process",
    )
    scenarios = (
        "adapter:expert-domain",
        "adapter:expert-qa",
        "adapter:expert-performance-reliability",
        "adapter:regression",
    )

    def supports(self, fingerprint: TargetFingerprint, config: TargetConfig) -> bool:
        return "python-project" in fingerprint.target_kinds

    def plan(self, profile_definition: dict[str, Any]) -> list[AdapterAction]:
        return [
            AdapterAction("python-manifest", "Inspect Python project metadata without importing project code.", "python-manifest-recon", "read-only", True, self.name),
            AdapterAction("python-compileall", "Compile Python source in the clone without executing project code.", "python-static-compile", "sandbox-mutation", True, self.name),
        ]

    def _root(self, context: AdapterContext) -> Path:
        return context.sandbox_target if context.sandbox_target.is_dir() else context.sandbox_target.parent

    def run_scenario(self, scenario: str, context: AdapterContext) -> list[Finding]:
        root = self._root(context)
        if scenario == "adapter:expert-domain":
            evidence: list[str] = []
            pyproject = root / "pyproject.toml"
            if pyproject.exists():
                try:
                    with pyproject.open("rb") as handle:
                        data = tomllib.load(handle)
                    project = data.get("project", {})
                    if isinstance(project, dict):
                        for key in ("name", "version", "requires-python"):
                            if key in project:
                                evidence.append(f"project.{key}={project[key]}")
                    evidence.append("pyproject_parse=ok")
                except Exception as exc:
                    return [_finding(
                        context, scenario, "BREAK",
                        f"pyproject.toml could not be parsed: {exc}",
                        severity="high",
                        evidence=[str(pyproject)],
                    )]
            evidence.append(f"python_files={sum(1 for _ in root.rglob('*.py'))}")
            return [_finding(context, scenario, "SURVIVED", "Python project metadata recon completed.", evidence=evidence)]
        compile_cmd = [sys.executable, "-m", "compileall", "-q", "."]
        if scenario == "adapter:expert-qa":
            return [_process_finding(
                context, scenario, "python-compileall",
                compile_cmd,
                timeout_seconds=30,
                success_summary="Python source compiled successfully without executing project code.",
            )]
        if scenario == "adapter:expert-performance-reliability":
            return [_process_finding(
                context, scenario, "python-compileall-performance",
                compile_cmd,
                timeout_seconds=30,
                success_summary="Python compile pass completed inside the 30s reliability window.",
            )]
        if scenario == "adapter:regression":
            first = _process_finding(
                context, scenario, "python-compileall-regression-1",
                compile_cmd,
                timeout_seconds=30,
                success_summary="First Python regression compile pass survived.",
            )
            second = _process_finding(
                context, scenario, "python-compileall-regression-2",
                compile_cmd,
                timeout_seconds=30,
                success_summary="Second Python regression compile pass survived.",
            )
            return [first, second]
        return []

class NodeProjectAdapter(BaseAdapter):
    name = "node-project"
    target_kind = "node-project"
    priority = 55
    capabilities = ("node-manifest-recon", "node-static-syntax", "sandbox-process")
    scenarios = ("adapter:expert-domain", "adapter:expert-qa")

    def supports(self, fingerprint: TargetFingerprint, config: TargetConfig) -> bool:
        return "node-project" in fingerprint.target_kinds

    def plan(self, profile_definition: dict[str, Any]) -> list[AdapterAction]:
        actions = [
            AdapterAction("node-manifest", "Inspect package.json without executing project code.", "node-manifest-recon", "read-only", True, self.name)
        ]
        if shutil.which("node"):
            actions.append(AdapterAction("node-check", "Run node --check on a bounded sample of JavaScript files.", "node-static-syntax", "read-only-process", True, self.name))
        return actions

    def _root(self, context: AdapterContext) -> Path:
        return context.sandbox_target if context.sandbox_target.is_dir() else context.sandbox_target.parent

    def _js_files(self, root: Path, limit: int = 20) -> list[Path]:
        found: list[Path] = []
        for current, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in {"node_modules", ".git", "dist", "build"}]
            for name in files:
                if Path(name).suffix.lower() not in {".js", ".mjs", ".cjs"}:
                    continue
                found.append(Path(current) / name)
                if len(found) >= limit:
                    return found
        return found

    def run_scenario(self, scenario: str, context: AdapterContext) -> list[Finding]:
        root = self._root(context)
        package = root / "package.json"
        if scenario == "adapter:expert-domain":
            try:
                data = json.loads(package.read_text(encoding="utf-8"))
            except Exception as exc:
                return [_finding(context, scenario, "BREAK", f"package.json parse failed: {exc}", severity="high")]
            evidence = []
            for key in ("name", "version", "type", "main"):
                if key in data:
                    evidence.append(f"{key}={data[key]}")
            scripts = data.get("scripts")
            if isinstance(scripts, dict):
                evidence.append("scripts=" + ",".join(sorted(str(k) for k in scripts)[:20]))
            return [_finding(context, scenario, "SURVIVED", "Node project manifest recon completed.", evidence=evidence)]

        node = shutil.which("node")
        if not node:
            return [_finding(
                context, scenario, "BLOCKED",
                "Node executable is unavailable, so static JavaScript syntax probes were not run.",
                action="Install Node or use a configured CLI probe in an environment that has it.",
            )]
        files = self._js_files(root)
        if not files:
            return [_finding(context, scenario, "BLOCKED", "No JavaScript files were found for node --check.")]
        findings: list[Finding] = []
        for index, file in enumerate(files):
            rel = file.relative_to(root).as_posix()
            findings.append(_process_finding(
                context,
                scenario,
                f"node-check-{index + 1}",
                [node, "--check", rel],
                timeout_seconds=10,
                cwd=root,
                success_summary=f"JavaScript syntax check survived: {rel}",
            ))
        return findings

class RustProjectAdapter(BaseAdapter):
    name = "rust-project"
    target_kind = "rust-project"
    priority = 50
    capabilities = ("cargo-manifest-recon",)
    scenarios = ("adapter:expert-domain",)

    def supports(self, fingerprint: TargetFingerprint, config: TargetConfig) -> bool:
        return "rust-project" in fingerprint.target_kinds

    def plan(self, profile_definition: dict[str, Any]) -> list[AdapterAction]:
        return [
            AdapterAction(
                "cargo-manifest",
                "Parse Cargo.toml without running cargo build scripts or project code.",
                "cargo-manifest-recon",
                "read-only",
                True,
                self.name,
            )
        ]

    def run_scenario(self, scenario: str, context: AdapterContext) -> list[Finding]:
        root = context.sandbox_target if context.sandbox_target.is_dir() else context.sandbox_target.parent
        cargo = root / "Cargo.toml"
        try:
            with cargo.open("rb") as handle:
                data = tomllib.load(handle)
        except Exception as exc:
            return [_finding(context, scenario, "BREAK", f"Cargo.toml parse failed: {exc}", severity="high")]
        package = data.get("package", {})
        evidence = []
        if isinstance(package, dict):
            for key in ("name", "version", "edition", "rust-version"):
                if key in package:
                    evidence.append(f"package.{key}={package[key]}")
        return [_finding(context, scenario, "SURVIVED", "Rust Cargo manifest recon completed without executing build code.", evidence=evidence)]

class OpaqueExecutableAdapter(BaseAdapter):
    name = "opaque-executable"
    target_kind = "executable-file"
    priority = 30
    capabilities = ("executable-detection", "explicit-probe-required")
    scenarios: tuple[str, ...] = ()

    def supports(self, fingerprint: TargetFingerprint, config: TargetConfig) -> bool:
        return "executable-file" in fingerprint.target_kinds

    def plan(self, profile_definition: dict[str, Any]) -> list[AdapterAction]:
        return [
            AdapterAction(
                "configure-executable",
                "Executable detected. Launch is intentionally disabled until chaospass.toml defines explicit safe probes.",
                "explicit-probe-required",
                "blocked-until-configured",
                False,
                self.name,
            )
        ]

class ConfiguredCLIAdapter(BaseAdapter):
    name = "configured-cli"
    target_kind = "configured-cli"
    priority = 100
    capabilities = ("configured-process-probes", "sandbox-user-profile", "exit-code-assertions", "output-assertions")

    def supports(self, fingerprint: TargetFingerprint, config: TargetConfig) -> bool:
        command = config.cli.get("command")
        allowed = config.chaos.get("allow_process_execution", False) is True
        return allowed and isinstance(command, list) and bool(command)

    def _probes(self, config: TargetConfig) -> list[dict[str, Any]]:
        probes = config.cli.get("probes", [])
        return [p for p in probes if isinstance(p, dict)] if isinstance(probes, list) else []

    def can_handle(self, scenario: str) -> bool:
        return scenario.startswith("adapter:")

    def can_handle_context(self, scenario: str, context: AdapterContext) -> bool:
        return any(p.get("scenario") == scenario for p in self._probes(context.config))

    def plan(self, profile_definition: dict[str, Any]) -> list[AdapterAction]:
        return [
            AdapterAction(
                "configured-cli-probes",
                "Execute only explicitly configured CLI probes with cwd and user-profile state redirected into the sandbox.",
                "configured-process-probes",
                "sandbox-process",
                True,
                self.name,
            )
        ]

    def run_scenario(self, scenario: str, context: AdapterContext) -> list[Finding]:
        probes = [p for p in self._probes(context.config) if p.get("scenario") == scenario]
        if not probes:
            return [_finding(
                context, scenario, "BLOCKED",
                f"Configured CLI has no probe mapped to {scenario}.",
                evidence=[f"config={context.config.source}"],
                action="Add a [[cli.probes]] entry for this scenario if the program can exercise it safely.",
            )]
        base = [str(x) for x in context.config.cli.get("command", [])]
        default_timeout = float(context.config.cli.get("timeout_seconds", 10))
        findings: list[Finding] = []
        for index, probe in enumerate(probes):
            probe_id = str(probe.get("id") or f"{scenario.replace(':', '_')}_{index}")
            args = [str(x) for x in probe.get("args", [])]
            expected_raw = probe.get("expected_exit_codes", [0])
            expected = {int(x) for x in expected_raw} if isinstance(expected_raw, list) else {0}
            timeout = float(probe.get("timeout_seconds", default_timeout))
            repeat = max(1, min(20, int(probe.get("repeat", 1))))
            rel_cwd = Path(str(probe.get("cwd", ".")))
            cwd = (context.sandbox_target if context.sandbox_target.is_dir() else context.sandbox_target.parent) / rel_cwd
            for run_index in range(repeat):
                label = f"cli-{probe_id}-{run_index + 1}"
                result = context.process_runner.run(base + args, label=label, cwd=cwd, timeout_seconds=timeout)
                evidence = [
                    "argv=" + " ".join(result.argv),
                    f"exit_code={result.exit_code}",
                    f"elapsed_seconds={result.elapsed_seconds:.4f}",
                    *result.evidence_files,
                ]
                expected_stdout = probe.get("stdout_contains")
                expected_stderr = probe.get("stderr_contains")
                failures: list[str] = []
                if result.timed_out:
                    failures.append("timeout")
                if result.exit_code not in expected:
                    failures.append(f"exit_code expected {sorted(expected)}")
                if isinstance(expected_stdout, str) and expected_stdout not in result.stdout:
                    failures.append(f"stdout missing {expected_stdout!r}")
                if isinstance(expected_stderr, str) and expected_stderr not in result.stderr:
                    failures.append(f"stderr missing {expected_stderr!r}")
                if failures:
                    findings.append(_finding(
                        context, scenario,
                        "BEND" if result.timed_out else "BREAK",
                        f"Configured CLI probe {probe_id} failed: {', '.join(failures)}.",
                        severity="medium" if result.timed_out else "high",
                        evidence=evidence,
                        reproduction=["Run the same configured probe in a disposable clone.", f"probe_id={probe_id}"],
                    ))
                else:
                    findings.append(_finding(
                        context, scenario, "SURVIVED",
                        f"Configured CLI probe {probe_id} passed.",
                        evidence=evidence,
                    ))
        return findings

class PlaybookDriverAdapter(BaseAdapter):
    """Translate persona intent into structured tasks for an external UI/computer driver."""

    name = "playbook-driver"
    target_kind = ""
    priority = 1
    capabilities = ("external-driver-instructions", "persona-opening-moves", "persona-signature-tactics")
    scenarios: tuple[str, ...] = ()

    def supports(self, fingerprint: TargetFingerprint, config: TargetConfig) -> bool:
        return True

    def plan(self, profile_definition: dict[str, Any]) -> list[AdapterAction]:
        profile_id = str(profile_definition.get("id", "profile"))
        actions: list[AdapterAction] = []
        for index, move in enumerate(profile_definition.get("opening_moves", []), 1):
            actions.append(AdapterAction(
                f"{profile_id}-opening-{index}",
                str(move),
                "external-driver-instructions",
                "driver-sandbox-only",
                False,
                self.name,
            ))
        for index, tactic in enumerate(profile_definition.get("signature_tactics", []), 1):
            if not isinstance(tactic, dict):
                continue
            name = str(tactic.get("name", f"tactic-{index}"))
            purpose = str(tactic.get("purpose", ""))
            steps = "; ".join(str(x) for x in tactic.get("actions", []))
            watch = ", ".join(str(x) for x in tactic.get("watch_for", []))
            description = f"{name}: {purpose}"
            if steps:
                description += f" Steps: {steps}."
            if watch:
                description += f" Watch for: {watch}."
            actions.append(AdapterAction(
                f"{profile_id}-tactic-{index}",
                description,
                "external-driver-instructions",
                "driver-sandbox-only",
                False,
                self.name,
            ))
        return actions

def builtin_adapters() -> list[BaseAdapter]:
    return [
        ConfiguredCLIAdapter(),
        PythonProjectAdapter(),
        NodeProjectAdapter(),
        RustProjectAdapter(),
        GitRepositoryAdapter(),
        OpaqueExecutableAdapter(),
        GenericFilesystemAdapter(),
        PlaybookDriverAdapter(),
    ]