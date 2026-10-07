#!/usr/bin/env python3
"""Scan public output for internal metadata, prompt leakage, and secrets."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _kb import print_result, relative, resolve_kb_root
from validate_report import BANNED_PATTERNS


EXTRA_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[oprsu]_[A-Za-z0-9]{20,}\b")),
    ("bearer credential", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}\b", re.IGNORECASE)),
    ("assigned secret", re.compile(r"\b(?:api[_-]?key|secret|password)\s*[:=]\s*[A-Za-z0-9._~+/=-]{12,}\b", re.IGNORECASE)),
    ("prompt or constitution leak", re.compile(r"\b(?:full system prompt|hidden system instructions|Use this as the instruction layer|Host system and developer instructions outrank this file)\b", re.IGNORECASE)),
    ("evidence directive echo", re.compile(r"\bSYSTEM:\s*(?:ignore|override)|ignore all prior (?:rules|instructions)", re.IGNORECASE)),
]


def load_internal_ids(root: Path) -> set[str]:
    ids: set[str] = set()
    for relative_path in ("taxonomy/patterns.yml", "taxonomy/norms.yml", "taxonomy/enforcement_outcomes.yml"):
        text = (root / relative_path).read_text(encoding="utf-8")
        ids.update(re.findall(r"(?m)^\s*-\s+id:\s*[\"']?([a-z0-9][a-z0-9-]+)", text))
    return ids


def scan_text(text: str, internal_ids: set[str]) -> list[str]:
    findings: list[str] = []
    for label, pattern in [*BANNED_PATTERNS, *EXTRA_PATTERNS]:
        if pattern.search(text):
            findings.append(label)
    lowered = text.lower()
    for internal_id in sorted(internal_ids):
        if re.search(rf"(?<![a-z0-9-]){re.escape(internal_id)}(?![a-z0-9-])", lowered):
            findings.append(f"internal taxonomy id: {internal_id}")
    return sorted(set(findings))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    parser.add_argument("--path", action="append", default=[], help="Public output file to scan; repeatable")
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    issues: list[str] = []
    warnings: list[str] = []
    internal_ids = load_internal_ids(root)

    paths = [Path(p).resolve() for p in args.path]
    if not paths:
        paths = sorted((root / "eval" / "report_samples").glob("*.md"))
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            issues.append(f"cannot read {path}: {exc}")
            continue
        for finding in scan_text(text, internal_ids):
            issues.append(f"{relative(path, root)}: {finding}")

    fixture_path = root / "eval" / "output_safety" / "cases.json"
    try:
        fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fixtures = []
        issues.append(f"cannot load output-safety fixtures: {exc}")
    seen: set[str] = set()
    for case in fixtures:
        case_id = case.get("id", "")
        if not case_id or case_id in seen:
            issues.append(f"invalid or duplicate output-safety fixture id: {case_id!r}")
            continue
        seen.add(case_id)
        actual = "reject" if scan_text(str(case.get("text", "")), internal_ids) else "pass"
        if actual != case.get("expected_status"):
            issues.append(f"{case_id}: expected {case.get('expected_status')}, got {actual}")
    warnings.append(f"output-safety summary: {len(paths)} public sample(s), {len(seen)} scanner fixtures")
    return print_result("Output-safety validation", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())

