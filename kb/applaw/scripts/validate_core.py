#!/usr/bin/env python3
"""Run the at-most-ten-check ordinary-maintenance validation gate."""

from __future__ import annotations

import argparse

from _kb import resolve_kb_root
from _validation_runner import load_plan, run_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    plan = load_plan()
    checks = plan.get("core_checks", [])
    maximum = int(plan.get("core_max_checks", 10))
    if not checks or len(checks) > maximum or maximum > 10:
        print(f"Core validation\nFAIL: invalid core plan size {len(checks)} with maximum {maximum}")
        return 1
    return run_plan(checks, root)


if __name__ == "__main__":
    raise SystemExit(main())

