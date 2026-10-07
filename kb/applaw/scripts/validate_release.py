#!/usr/bin/env python3
"""Run every release check, including strict gold review and checksums."""

from __future__ import annotations

import argparse

from _kb import resolve_kb_root
from _validation_runner import load_plan, run_plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    if not (root / "SHA256SUMS.txt").is_file():
        print("Release validation\nFAIL: SHA256SUMS.txt is required; run the complete gate from a finalized portable release root")
        return 1
    return run_plan(load_plan().get("release_checks", []), root)


if __name__ == "__main__":
    raise SystemExit(main())

