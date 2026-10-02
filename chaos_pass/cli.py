from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adapters import discover_adapters
from .config import load_target_config
from .profiles import load_profile_definition, profile_names
from .regressions import load_regression_cases
from .reporting import write_json, write_markdown
from .runner import run
from .safety import ensure_output_outside_target

DEFAULT_MAX_CLONE_BYTES = 512 * 1024 * 1024

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chaos-pass", description="Zero-trace adversarial QA")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser(
        "list-profiles",
        help="List built-in profiles",
        description="List every built-in Chaos Pass persona/profile.",
    )

    dp = sub.add_parser(
        "describe-profile",
        help="Print a complete persona attack playbook",
        description="Print the complete machine-readable persona attack playbook for one profile.",
    )
    dp.add_argument("profile", choices=profile_names())

    lr = sub.add_parser(
        "list-regressions",
        help="List historical regression cases for a target",
        description="List historical Regression Archaeologist cases discovered in the target's regressions folder.",
    )
    lr.add_argument("--target", required=True, type=Path)

    ip = sub.add_parser(
        "inspect-target",
        help="Read-only target fingerprint and adapter detection",
        description="Inspect a target read-only, fingerprint its type, and show which adapters/capabilities apply.",
    )
    ip.add_argument("--target", required=True, type=Path)
    ip.add_argument("--config", type=Path, default=None)

    pp = sub.add_parser(
        "plan",
        help="Build a read-only persona-to-adapter attack plan",
        description="Build a read-only persona-to-adapter attack plan without running destructive probes.",
    )
    pp.add_argument("--target", required=True, type=Path)
    pp.add_argument("--profile", required=True, choices=profile_names())
    pp.add_argument("--config", type=Path, default=None)

    rp = sub.add_parser(
        "run",
        help="Run Chaos Pass against an authorized target",
        description="Run Chaos Pass against an authorized target using disposable isolation, evidence capture, teardown, and original-integrity verification.",
    )
    rp.add_argument("--target", required=True, type=Path)
    rp.add_argument("--profile", default="full-chaos-pass", choices=profile_names())
    rp.add_argument("--output", type=Path, default=Path.cwd() / "reports")
    rp.add_argument("--config", type=Path, default=None)
    rp.add_argument("--max-clone-bytes", type=int, default=DEFAULT_MAX_CLONE_BYTES)
    rp.add_argument("--seed", type=int, default=None)
    return parser

def _inspect(target: Path, config_path: Path | None) -> dict:
    target = target.resolve()
    config = load_target_config(target, config_path)
    fingerprint, adapters = discover_adapters(target, config)
    return {
        "fingerprint": fingerprint.to_dict(),
        "adapters": adapters.names,
        "target_kinds": adapters.target_kinds,
        "capabilities": adapters.capabilities,
        "config_source": str(config.source) if config.source else None,
        "configured_process_execution": config.chaos.get("allow_process_execution", False) is True,
    }

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "list-profiles":
        for name in profile_names():
            print(name)
        return 0

    if args.command == "describe-profile":
        print(json.dumps(load_profile_definition(args.profile), indent=2, ensure_ascii=False))
        return 0

    if args.command == "list-regressions":
        cases = [case.to_dict() for case in load_regression_cases(args.target.resolve())]
        print(json.dumps(cases, indent=2, ensure_ascii=False))
        return 0

    if args.command == "inspect-target":
        print(json.dumps(_inspect(args.target, args.config), indent=2, ensure_ascii=False))
        return 0

    if args.command == "plan":
        target = args.target.resolve()
        config = load_target_config(target, args.config)
        fingerprint, adapters = discover_adapters(target, config)
        definition = load_profile_definition(args.profile)
        plan = adapters.plan(definition)
        result = {
            "fingerprint": fingerprint.to_dict(),
            "config_source": str(config.source) if config.source else None,
            "plan": plan.to_dict(),
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    target = args.target.resolve()
    output = args.output.resolve()
    ensure_output_outside_target(target, output)

    report = run(
        target,
        args.profile,
        args.max_clone_bytes,
        args.seed,
        config_path=args.config,
        evidence_root=output,
    )
    json_path = output / f"{report.run_id}.json"
    md_path = output / f"{report.run_id}.md"
    write_json(report, json_path)
    write_markdown(report, md_path)

    print(f"Chaos Pass: {report.run_id}")
    print(f"Adapters: {', '.join(report.adapter_names) or 'none'}")
    print(f"Original integrity: {'PASS' if report.integrity_passed else 'FAIL'}")
    print(f"Report: {md_path}")
    print(f"JSON:   {json_path}")
    if report.evidence_path:
        print(f"Evidence: {report.evidence_path}")
    return 0 if report.integrity_passed else 2