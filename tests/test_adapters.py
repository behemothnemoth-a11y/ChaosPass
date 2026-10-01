import json
import os
from pathlib import Path
import sys
import subprocess
import shutil
import tempfile
import unittest
from unittest.mock import patch

from chaos_pass.adapters import AdapterContext, discover_adapters, fingerprint_target
from chaos_pass.config import TargetConfig, load_target_config
from chaos_pass.processes import SandboxProcessRunner
from chaos_pass.profiles import load_profile_definition
from chaos_pass.runner import run
from chaos_pass.safety import SafetyError

class AdapterEngineTests(unittest.TestCase):
    def test_python_project_adapter_is_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "demo"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )
            config = TargetConfig({}, None)
            fingerprint, stack = discover_adapters(root, config)
            self.assertIn("python-project", fingerprint.target_kinds)
            self.assertIn("python-project", stack.names)
            self.assertIn("filesystem", stack.names)

    def test_node_and_rust_markers_get_specialized_adapters(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "package.json").write_text('{"name":"demo","version":"1.0.0"}', encoding="utf-8")
            (root / "Cargo.toml").write_text(
                '[package]\nname = "demo"\nversion = "0.1.0"\nedition = "2021"\n',
                encoding="utf-8",
            )
            fingerprint, stack = discover_adapters(root, TargetConfig({}, None))
            self.assertIn("node-project", fingerprint.target_kinds)
            self.assertIn("rust-project", fingerprint.target_kinds)
            self.assertIn("node-project", stack.names)
            self.assertIn("rust-project", stack.names)

    def test_process_runner_redirects_user_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "sandbox"
            root.mkdir()
            evidence = Path(temp) / "evidence"
            runner = SandboxProcessRunner(root, evidence_dir=evidence)
            code = (
                "import os,pathlib;"
                "p=pathlib.Path(os.environ['HOME'])/'marker.txt';"
                "p.write_text('sandboxed',encoding='utf-8');"
                "print(p)"
            )
            result = runner.run([sys.executable, "-c", code], label="home-redirect")
            self.assertEqual(result.exit_code, 0)
            self.assertTrue((runner.runtime_root / "home" / "marker.txt").exists())
            self.assertFalse((Path.home() / "marker.txt").exists())
            self.assertTrue(result.evidence_files)

    def test_process_runner_rejects_cwd_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            sandbox = Path(temp) / "sandbox"
            outside = Path(temp) / "outside"
            sandbox.mkdir()
            outside.mkdir()
            runner = SandboxProcessRunner(sandbox)
            with self.assertRaises(SafetyError):
                runner.run([sys.executable, "-c", "print('x')"], label="escape", cwd=outside)

    def test_process_runner_rejects_absolute_argument_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            sandbox = base / "sandbox"
            sandbox.mkdir()
            outside = base / "outside.txt"
            outside.write_text("x", encoding="utf-8")
            runner = SandboxProcessRunner(sandbox)
            with self.assertRaises(SafetyError):
                runner.run(
                    [sys.executable, str(outside)],
                    label="absolute-arg-escape",
                )

    def test_process_environment_strips_secrets_and_denies_network_by_default(self):
        with tempfile.TemporaryDirectory() as temp:
            sandbox = Path(temp) / "sandbox"
            sandbox.mkdir()
            with patch.dict(os.environ, {"CHAOS_TEST_TOKEN": "secret-value"}, clear=False):
                runner = SandboxProcessRunner(sandbox)
                env = runner.sanitized_environment()
            self.assertNotIn("CHAOS_TEST_TOKEN", env)
            self.assertEqual(env["HTTPS_PROXY"], "http://127.0.0.1:9")
            self.assertEqual(env["CHAOS_PASS_NETWORK_POLICY"], "deny-best-effort")
            self.assertTrue(env["CARGO_HOME"].startswith(str(runner.runtime_root)))
            self.assertTrue(env["NPM_CONFIG_CACHE"].startswith(str(runner.runtime_root)))

    def test_cli_config_does_not_enable_execution_without_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            (target / "app.py").write_text("print('x')\n", encoding="utf-8")
            (target / "chaospass.toml").write_text(
                "[cli]\ncommand = [\"python\", \"app.py\"]\n",
                encoding="utf-8",
            )
            config = load_target_config(target)
            _, stack = discover_adapters(target, config)
            self.assertNotIn("configured-cli", stack.names)

    def test_opaque_executable_requires_explicit_driver_or_cli_config(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "demo.exe"
            target.write_bytes(b"not-a-real-executable")
            config = TargetConfig({}, None)
            fingerprint, stack = discover_adapters(target, config)
            self.assertIn("executable-file", fingerprint.target_kinds)
            self.assertIn("opaque-executable", stack.names)
            plan = stack.plan(load_profile_definition("ui-gremlin"))
            self.assertTrue(any(
                action.source_adapter == "opaque-executable"
                and not action.executable
                for action in plan.actions
            ))

    def test_configured_cli_probe_runs_only_in_clone(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target = base / "target"
            target.mkdir()
            script = target / "app.py"
            script.write_text(
                "import os, pathlib, sys\n"
                "pathlib.Path(os.environ['HOME'], 'cli-home.txt').write_text('x', encoding='utf-8')\n"
                "print('CHAOS_HELP' if '--help' in sys.argv else 'RUN')\n",
                encoding="utf-8",
            )
            exe = json.dumps(sys.executable)
            (target / "chaospass.toml").write_text(
                "[chaospass]\n"
                "allow_process_execution = true\n\n"
                "[cli]\n"
                f"command = [{exe}, \"app.py\"]\n"
                "timeout_seconds = 5\n\n"
                "[[cli.probes]]\n"
                'id = "help"\n'
                'scenario = "adapter:expert-domain"\n'
                'args = ["--help"]\n'
                "expected_exit_codes = [0]\n"
                'stdout_contains = "CHAOS_HELP"\n',
                encoding="utf-8",
            )
            before = sorted(p.relative_to(target).as_posix() for p in target.rglob("*"))
            report = run(
                target,
                "expert-baseline",
                16 * 1024 * 1024,
                seed=7,
                evidence_root=base / "reports",
            )
            after = sorted(p.relative_to(target).as_posix() for p in target.rglob("*"))
            self.assertTrue(report.integrity_passed)
            self.assertEqual(before, after)
            self.assertIn("configured-cli", report.adapter_names)
            self.assertTrue(any(
                f.adapter == "configured-cli"
                and f.scenario == "adapter:expert-domain"
                and f.status == "SURVIVED"
                for f in report.findings
            ))
            self.assertFalse((target / "cli-home.txt").exists())
            self.assertTrue((Path(report.evidence_path) / "plan-expert-baseline.json").exists())

    @unittest.skipUnless(shutil.which("git"), "git unavailable")
    def test_git_repository_adapter_runs_real_read_only_probes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "README.md").write_text("# demo\n", encoding="utf-8")
            subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
            subprocess.run(
                [
                    "git", "-c", "user.name=Chaos Pass",
                    "-c", "user.email=chaos@example.invalid",
                    "commit", "-q", "-m", "initial",
                ],
                cwd=root,
                check=True,
            )
            report = run(root, "expert-baseline", 32 * 1024 * 1024, seed=8)
            self.assertTrue(report.integrity_passed)
            self.assertIn("git-repository", report.adapter_names)
            self.assertTrue(any(
                f.adapter == "git-repository"
                and f.scenario == "adapter:expert-domain"
                and f.status == "SURVIVED"
                for f in report.findings
            ))
            self.assertFalse(any(
                f.adapter == "git-repository" and f.status in {"BREAK", "CATASTROPHIC"}
                for f in report.findings
            ))

    def test_persona_plan_contains_adapter_actions(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "demo"\nversion = "0.1.0"\n',
                encoding="utf-8",
            )
            config = load_target_config(root)
            _, stack = discover_adapters(root, config)
            plan = stack.plan(load_profile_definition("expert-baseline"))
            self.assertIn("python-project", plan.adapter_names)
            self.assertTrue(any(action.executable for action in plan.actions))
            self.assertTrue(any(action.source_adapter == "python-project" for action in plan.actions))
            self.assertTrue(any(
                not action.executable and action.source_adapter == "playbook-driver"
                for action in plan.actions
            ))

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_escaping_junction_is_recorded_and_blocks_run(self):
        from chaos_pass.safety import snapshot_path

        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target = base / "target"
            outside = base / "outside"
            target.mkdir()
            outside.mkdir()
            (outside / "secret.txt").write_text("outside", encoding="utf-8")
            junction = target / "escape"
            command = (
                f"New-Item -ItemType Junction -Path '{junction}' "
                f"-Target '{outside}' | Out-Null"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            snapshot = snapshot_path(target)
            self.assertIn("escape", snapshot)
            self.assertEqual(snapshot["escape"].kind, "junction")
            self.assertFalse(any(key.startswith("escape/") for key in snapshot))

            report = run(target, "chaos-goblin", 16 * 1024 * 1024, seed=4)
            self.assertTrue(report.integrity_passed)
            self.assertTrue(any(
                f.profile == "preflight"
                and f.scenario == "sandbox_creation"
                and f.status == "BLOCKED"
                for f in report.findings
            ))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink unavailable")
    def test_escaping_symlink_blocks_full_run_when_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            target = base / "target"
            outside = base / "outside"
            target.mkdir()
            outside.mkdir()
            (outside / "secret.txt").write_text("do not touch", encoding="utf-8")
            try:
                os.symlink(outside, target / "escape", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlink creation not permitted: {exc}")
            report = run(target, "chaos-goblin", 16 * 1024 * 1024, seed=3)
            self.assertTrue(report.integrity_passed)
            self.assertTrue(any(
                f.profile == "preflight"
                and f.scenario == "sandbox_creation"
                and f.status == "BLOCKED"
                for f in report.findings
            ))

if __name__ == "__main__":
    unittest.main()