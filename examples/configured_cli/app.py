from __future__ import annotations

import sys

if "--help" in sys.argv:
    print("Chaos Pass demo CLI")
    print("usage: python app.py [--help|--self-check]")
    raise SystemExit(0)

if "--self-check" in sys.argv:
    print("SELF_CHECK_OK")
    raise SystemExit(0)

if len(sys.argv) > 1:
    print(f"unknown option: {sys.argv[1]}", file=sys.stderr)
    raise SystemExit(2)

print("demo")