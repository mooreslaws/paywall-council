#!/usr/bin/env python3
"""Run report-contract and public-output safety checks as one validation phase."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable

from _kb import resolve_kb_root
import validate_output_safety
import validate_report


def run_with_kb(check: Callable[[], int], root: str) -> int:
    original = sys.argv
    try:
        sys.argv = [original[0], "--kb", root]
        return int(check())
    finally:
        sys.argv = original


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()
    root = str(resolve_kb_root(args.kb))
    results = [run_with_kb(validate_report.main, root), run_with_kb(validate_output_safety.main, root)]
    return 1 if any(results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

