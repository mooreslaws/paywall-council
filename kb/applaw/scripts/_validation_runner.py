#!/usr/bin/env python3
"""Shared in-process runner for documented composite validation plans."""

from __future__ import annotations

import importlib
import json
import re
import sys
from pathlib import Path
from typing import Any


PLAN_PATH = Path(__file__).with_name("validation_plan.json")


def load_plan() -> dict[str, Any]:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if not isinstance(plan, dict):
        raise ValueError("validation_plan.json must contain an object")
    return plan


def run_check(entry: dict[str, Any], root: Path) -> int:
    module_name = str(entry["module"])
    print(f"\n=== {entry['name']} ({module_name}) ===")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", module_name):
        raise ValueError(f"invalid validation module name: {module_name!r}")
    expected_path = Path(__file__).with_name(f"{module_name}.py").resolve()
    if not expected_path.is_file():
        raise ValueError(f"validation module is not a sibling script: {module_name}")
    module = importlib.import_module(module_name)
    imported_path = Path(str(getattr(module, "__file__", ""))).resolve()
    if imported_path != expected_path:
        raise ValueError(f"validation module resolved outside the package: {module_name}")
    if module_name == "verify_checksums":
        return int(module.verify_manifest(root))
    original = sys.argv
    try:
        sys.argv = [module_name, "--kb", str(root), *[str(value) for value in entry.get("args", [])]]
        return int(module.main())
    finally:
        sys.argv = original


def run_plan(entries: list[dict[str, Any]], root: Path) -> int:
    failures: list[str] = []
    for entry in entries:
        try:
            result = run_check(entry, root)
        except Exception as exc:
            result = 1
            print(f"ERROR: {entry.get('module')} raised: {exc}")
        if result:
            failures.append(str(entry.get("module")))
    print("\nComposite validation summary")
    if failures:
        print(f"FAIL: {len(failures)} check(s): {', '.join(failures)}")
        return 1
    print(f"PASS: {len(entries)} check(s)")
    return 0
