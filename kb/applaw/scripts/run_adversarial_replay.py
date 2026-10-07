#!/usr/bin/env python3
"""Self-test replay rules or grade saved host-produced adversarial transcripts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _kb import print_result, resolve_kb_root


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def grade(rule: dict, text: str) -> list[str]:
    failures: list[str] = []
    for pattern in rule.get("must_match", []):
        if not re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            failures.append(f"missing required pattern: {pattern}")
    for pattern in rule.get("must_not_match", []):
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            failures.append(f"matched forbidden pattern: {pattern}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Grade saved transcripts. This runner never invokes a model."
    )
    parser.add_argument("--kb", default=None)
    parser.add_argument("--transcript-dir", help="Directory containing <case-id>.txt host-produced transcripts")
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    replay_root = root / "eval" / "adversarial_replays"
    issues: list[str] = []
    warnings: list[str] = []
    try:
        rules = load_json(replay_root / "rules.json")
    except (OSError, json.JSONDecodeError) as exc:
        return print_result("Adversarial transcript replay", [f"cannot load replay rules: {exc}"], [])

    by_id: dict[str, dict] = {}
    for rule in rules:
        case_id = str(rule.get("id", ""))
        if not case_id or case_id in by_id:
            issues.append(f"invalid or duplicate replay rule id: {case_id!r}")
            continue
        by_id[case_id] = rule
        source = root / str(rule.get("source_card", ""))
        if not source.is_file():
            issues.append(f"{case_id}: missing source adversarial card: {rule.get('source_card')}")
        if not rule.get("must_match") or not rule.get("must_not_match"):
            issues.append(f"{case_id}: rules require both must_match and must_not_match checks")

    if args.transcript_dir:
        transcript_dir = Path(args.transcript_dir).resolve()
        for case_id, rule in by_id.items():
            path = transcript_dir / f"{case_id}.txt"
            if not path.is_file():
                issues.append(f"{case_id}: missing transcript {path}")
                continue
            for failure in grade(rule, path.read_text(encoding="utf-8")):
                issues.append(f"{case_id}: {failure}")
        warnings.append(f"graded {len(by_id)} host-produced transcript(s); no model was invoked")
    else:
        try:
            cases = load_json(replay_root / "cases.json")
        except (OSError, json.JSONDecodeError) as exc:
            cases = []
            issues.append(f"cannot load replay self-tests: {exc}")
        case_ids: set[str] = set()
        for case in cases:
            case_id = str(case.get("id", ""))
            if case_id in case_ids:
                issues.append(f"duplicate replay self-test id: {case_id}")
                continue
            case_ids.add(case_id)
            rule = by_id.get(case_id)
            if not rule:
                issues.append(f"{case_id}: self-test has no rule")
                continue
            safe_failures = grade(rule, str(case.get("pass_transcript", "")))
            unsafe_failures = grade(rule, str(case.get("fail_transcript", "")))
            if safe_failures:
                issues.append(f"{case_id}: known-safe transcript failed: {'; '.join(safe_failures)}")
            if not unsafe_failures:
                issues.append(f"{case_id}: known-unsafe transcript was accepted")
        if set(by_id) != case_ids:
            issues.append("replay rule ids and self-test ids must match exactly")
        warnings.append(f"replay self-test summary: {len(case_ids)} rule pair(s); no model was invoked")

    return print_result("Adversarial transcript replay", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())

