from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Mapping, Sequence

from .safety import SafetyError

SENSITIVE_ENV_MARKERS = (
    "TOKEN", "SECRET", "PASSWORD", "PASSWD", "API_KEY",
    "ACCESS_KEY", "PRIVATE_KEY", "CREDENTIAL",
)
SENSITIVE_ENV_EXACT = {
    "SSH_AUTH_SOCK",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "DATABASE_URL",
}

@dataclass(slots=True)
class ProcessResult:
    label: str
    argv: list[str]
    cwd: str
    exit_code: int | None
    elapsed_seconds: float
    timed_out: bool
    stdout: str
    stderr: str
    evidence_files: list[str]

    @property
    def succeeded(self) -> bool:
        return not self.timed_out and self.exit_code == 0

    def to_dict(self) -> dict:
        return asdict(self)

def _inside(child: Path, parent: Path) -> bool:
    child = child.resolve()
    parent = parent.resolve()
    return child == parent or parent in child.parents

def _looks_sensitive_env(name: str) -> bool:
    upper = name.upper()
    return upper in SENSITIVE_ENV_EXACT or any(marker in upper for marker in SENSITIVE_ENV_MARKERS)

class SandboxProcessRunner:
    """Run explicitly approved probes with process state redirected into a disposable environment."""

    def __init__(
        self,
        sandbox_root: Path,
        evidence_dir: Path | None = None,
        max_output_chars: int = 40_000,
        *,
        allow_network: bool = False,
    ) -> None:
        self.sandbox_root = sandbox_root.resolve()
        self.evidence_dir = evidence_dir.resolve() if evidence_dir else None
        self.max_output_chars = max_output_chars
        self.allow_network = allow_network
        self.runtime_root = self.sandbox_root.parent / ".chaos_pass_runtime"
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self._prepare_runtime_dirs()

    def _prepare_runtime_dirs(self) -> None:
        for name in (
            "home", "appdata", "localappdata", "tmp", "cache", "config",
            "cargo", "npm-cache", "pip-cache", "gradle", "dotnet", "nuget",
        ):
            (self.runtime_root / name).mkdir(parents=True, exist_ok=True)
        if self.evidence_dir:
            self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def _environment(self, extra: Mapping[str, str] | None) -> dict[str, str]:
        env = {k: v for k, v in os.environ.items() if not _looks_sensitive_env(k)}
        home = self.runtime_root / "home"
        appdata = self.runtime_root / "appdata"
        local = self.runtime_root / "localappdata"
        tmp = self.runtime_root / "tmp"
        env.update({
            "HOME": str(home),
            "USERPROFILE": str(home),
            "APPDATA": str(appdata),
            "LOCALAPPDATA": str(local),
            "TEMP": str(tmp),
            "TMP": str(tmp),
            "XDG_CACHE_HOME": str(self.runtime_root / "cache"),
            "XDG_CONFIG_HOME": str(self.runtime_root / "config"),
            "CARGO_HOME": str(self.runtime_root / "cargo"),
            "NPM_CONFIG_CACHE": str(self.runtime_root / "npm-cache"),
            "PIP_CACHE_DIR": str(self.runtime_root / "pip-cache"),
            "GRADLE_USER_HOME": str(self.runtime_root / "gradle"),
            "DOTNET_CLI_HOME": str(self.runtime_root / "dotnet"),
            "NUGET_PACKAGES": str(self.runtime_root / "nuget"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_TERMINAL_PROMPT": "0",
            "CHAOS_PASS_SANDBOX": "1",
            "CHAOS_PASS_ORIGINAL_FORBIDDEN": "1",
            "CHAOS_PASS_NETWORK_POLICY": "allow" if self.allow_network else "deny-best-effort",
        })
        if not self.allow_network:
            dead_proxy = "http://127.0.0.1:9"
            env.update({
                "HTTP_PROXY": dead_proxy,
                "HTTPS_PROXY": dead_proxy,
                "ALL_PROXY": dead_proxy,
                "http_proxy": dead_proxy,
                "https_proxy": dead_proxy,
                "all_proxy": dead_proxy,
                "NO_PROXY": "localhost,127.0.0.1,::1",
                "no_proxy": "localhost,127.0.0.1,::1",
            })
        if extra:
            env.update({str(k): str(v) for k, v in extra.items()})
        return env

    def sanitized_environment(self, extra: Mapping[str, str] | None = None) -> dict[str, str]:
        """Exposed for tests and adapter diagnostics."""
        return self._environment(extra)

    def _validate_cwd(self, cwd: Path) -> Path:
        resolved = cwd.resolve()
        if not _inside(resolved, self.sandbox_root):
            raise SafetyError(f"Process cwd escapes sandbox: {resolved}")
        if not resolved.is_dir():
            raise SafetyError(f"Process cwd is not a directory: {resolved}")
        return resolved

    def _validate_args(self, argv: Sequence[str]) -> list[str]:
        if not argv:
            raise SafetyError("Process argv may not be empty.")
        normalized = [str(x) for x in argv]
        for arg in normalized[1:]:
            if not arg or arg.startswith("-"):
                continue
            candidate = Path(arg)
            if candidate.is_absolute() and not _inside(candidate, self.sandbox_root):
                raise SafetyError(f"Absolute process argument escapes sandbox: {arg}")
        return normalized

    def _write_evidence(self, result: ProcessResult) -> list[str]:
        if not self.evidence_dir:
            return []
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in result.label)[:80]
        stem = self.evidence_dir / safe
        stdout_path = stem.with_suffix(".stdout.txt")
        stderr_path = stem.with_suffix(".stderr.txt")
        meta_path = stem.with_suffix(".process.json")
        stdout_path.write_text(result.stdout, encoding="utf-8", errors="replace")
        stderr_path.write_text(result.stderr, encoding="utf-8", errors="replace")
        meta = result.to_dict()
        meta["evidence_files"] = []
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        return [str(stdout_path), str(stderr_path), str(meta_path)]

    def _terminate_tree(self, proc: subprocess.Popen[str]) -> None:
        if proc.poll() is not None:
            return
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    shell=False,
                )
                return
            except Exception:
                pass
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
                return
            except Exception:
                pass
        try:
            proc.kill()
        except Exception:
            pass

    def run(
        self,
        argv: Sequence[str],
        *,
        label: str,
        cwd: Path | None = None,
        timeout_seconds: float = 10.0,
        env: Mapping[str, str] | None = None,
    ) -> ProcessResult:
        safe_argv = self._validate_args(argv)
        safe_cwd = self._validate_cwd(cwd or self.sandbox_root)
        started = time.perf_counter()
        timed_out = False
        creationflags = 0
        popen_kwargs: dict = {}
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_kwargs["start_new_session"] = True

        proc = subprocess.Popen(
            safe_argv,
            cwd=safe_cwd,
            env=self._environment(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            shell=False,
            creationflags=creationflags,
            **popen_kwargs,
        )
        try:
            stdout, stderr = proc.communicate(timeout=max(0.1, float(timeout_seconds)))
        except subprocess.TimeoutExpired:
            timed_out = True
            self._terminate_tree(proc)
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except Exception:
                stdout, stderr = "", ""
        elapsed = time.perf_counter() - started
        result = ProcessResult(
            label=label,
            argv=safe_argv,
            cwd=str(safe_cwd),
            exit_code=proc.returncode,
            elapsed_seconds=elapsed,
            timed_out=timed_out,
            stdout=(stdout or "")[: self.max_output_chars],
            stderr=(stderr or "")[: self.max_output_chars],
            evidence_files=[],
        )
        result.evidence_files = self._write_evidence(result)
        return result