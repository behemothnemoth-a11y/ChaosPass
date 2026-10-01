from __future__ import annotations

import argparse
from pathlib import Path

from .profiles import profile_names
from .reporting import write_json, write_markdown
from .runner import run
from .safety import ensure_output_outside_target

DEFAULT_MAX_CLONE_BYTES = 512 * 1024 * 1024

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chaos-pass", description="Zero-trace adversarial QA")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list-profiles", help="List built-in profiles")

    rp = sub.add_parser("run", help="Run Chaos Pass against an authorized target")
    rp.add_argument("--target", required=True, type=Path)
    rp.add_argument("--profile", default="full-chaos-pass", choices=profile_names())
    rp.add_argument("--output", type=Path, default=Path.cwd() / "reports")
    rp.add_argument("--max-clone-bytes", type=int, default=DEFAULT_MAX_CLONE_BYTES)
    rp.add_argument("--seed", type=int, default=None)
    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "list-profiles":
        for name in profile_names():
            print(name)
        return 0

    target = args.target.resolve()
    output = args.output.resolve()
    ensure_output_outside_target(target, output)

    report = run(target, args.profile, args.max_clone_bytes, args.seed)
    json_path = output / f"{report.run_id}.json"
    md_path = output / f"{report.run_id}.md"
    write_json(report, json_path)
    write_markdown(report, md_path)

    print(f"Chaos Pass: {report.run_id}")
    print(f"Original integrity: {'PASS' if report.integrity_passed else 'FAIL'}")
    print(f"Report: {md_path}")
    print(f"JSON:   {json_path}")
    return 0 if report.integrity_passed else 2
