#!/usr/bin/env python3
"""Validate context-aware resource admission and exact boundary fixtures."""

from __future__ import annotations

import argparse
import json

from _kb import print_result, resolve_kb_root
from preflight_inputs import METRICS, OCCUPIED_COMPONENTS, evaluate_admission, load_limits


EXPECTED = {
    "ocr_characters": (100000, 200000, "characters"),
    "evidence_tokens": (24000, 32000, "tokens"),
    "processing_seconds": (120, 180, "seconds"),
}
HOST_CONTROLS = {
    "attachment count",
    "aggregate and per-file upload bytes",
    "image dimensions and pixel count",
    "PDF page count",
    "archive expansion and decompression limits",
    "MIME and file-signature validation",
    "authentication, authorization, quotas, and rate limits",
}
REQUIRED_BOUNDARY_CASES = {
    "evidence-below-effective-capacity",
    "evidence-warning-exact",
    "evidence-hard-exact",
    "evidence-above-hard",
    "evidence-24k-does-not-fit-32k-context",
    "evidence-fits-64k-with-reserves",
    "cached-input-still-occupies-context",
    "zero-remaining-evidence-capacity",
    "missing-context-window-metadata",
    "inconsistent-occupied-input-components",
    "declared-retrieved-kb-overlap",
    "screenshot-batch-admission-pass",
    "screenshot-batch-admission-reject",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    issues: list[str] = []
    warnings: list[str] = []

    try:
        config = load_limits(root)
    except (OSError, json.JSONDecodeError) as exc:
        return print_result("Resource-limit validation", [f"cannot load RESOURCE_LIMITS.json: {exc}"], [])

    if config.get("schema_version") != "2.0":
        issues.append("RESOURCE_LIMITS.json schema_version must be 2.0")
    try:
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        package_version = package.get("version")
    except (OSError, json.JSONDecodeError) as exc:
        package_version = None
        issues.append(f"cannot load package.json version: {exc}")
    if config.get("release_version") != package_version:
        issues.append("RESOURCE_LIMITS.json release_version must match package.json")
    if config.get("scope") != "agent-side post-ingestion evidence processing":
        issues.append("RESOURCE_LIMITS.json must be scoped to agent-side post-ingestion evidence processing")
    budgets = config.get("budgets", {})
    if set(budgets) != set(METRICS):
        issues.append(f"budgets must contain only: {', '.join(METRICS)}")
    for name, (warning, hard, unit) in EXPECTED.items():
        item = budgets.get(name, {})
        if (item.get("warning"), item.get("hard"), item.get("unit")) != (warning, hard, unit):
            issues.append(f"{name} must be warning={warning}, hard={hard}, unit={unit}")
    evidence_role = str(budgets.get("evidence_tokens", {}).get("role", ""))
    if "absolute" not in evidence_role or "lower" not in evidence_role:
        issues.append("evidence token values must be described as absolute ceilings with lower runtime-effective thresholds")

    contract = config.get("accounting_contract", {})
    if contract.get("context_window_tokens_source") != "host-supplied; no package default":
        issues.append("context-window accounting must be host-supplied with no package default")
    if tuple(contract.get("occupied_input_component_fields", [])) != OCCUPIED_COMPONENTS:
        issues.append("occupied_input_component_fields must enumerate the four non-overlapping input components in order")
    for phrase in [
        "retrieved KB tokens",
        "candidate evidence tokens",
        "sum exactly",
        "non-finite",
        "rejected",
    ]:
        if phrase.lower() not in str(contract).lower():
            issues.append(f"accounting contract is missing required concept: {phrase}")
    if "floor" not in str(contract.get("effective_warning_formula", "")):
        issues.append("effective warning formula must scale the warning threshold when context capacity is lower")
    if set(config.get("host_webapp_responsibility", [])) != HOST_CONTROLS:
        issues.append("host_webapp_responsibility must enumerate the release boundary exactly")
    if "Never silently truncate evidence." not in config.get("hard_limit_action", ""):
        issues.append("hard_limit_action must prohibit silent truncation")
    notes = " ".join(config.get("notes", []))
    for phrase in ["not claims", "byte-derived estimate", "complete screenshot batch"]:
        if phrase.lower() not in notes.lower():
            issues.append(f"RESOURCE_LIMITS.json notes missing: {phrase}")

    fixture_path = root / "eval" / "resource_limits" / "cases.json"
    try:
        fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        fixtures = []
        issues.append(f"cannot load resource-limit fixtures: {exc}")
    seen: set[str] = set()
    statuses: set[str] = set()
    for case in fixtures:
        case_id = str(case.get("id", ""))
        if not case_id or case_id in seen:
            issues.append(f"invalid or duplicate resource-limit fixture id: {case_id!r}")
            continue
        seen.add(case_id)
        expected = str(case.get("expected_status", ""))
        statuses.add(expected)
        try:
            result = evaluate_admission(
                config,
                case["counters"],
                admission_scope=str(case.get("admission_scope", "single_evidence")),
                batch_item_count=case.get("batch_item_count"),
            )
        except Exception as exc:
            issues.append(f"{case_id}: evaluator raised instead of returning structured output: {exc}")
            continue
        if result.get("status") != expected:
            issues.append(f"{case_id}: expected {expected}, got {result.get('status')}")
        accounting = result.get("accounting", {})
        evidence = result.get("metrics", {}).get("evidence_tokens", {})
        expected_fields = {
            "expected_available_evidence_tokens": accounting.get("available_evidence_tokens"),
            "expected_effective_warning": evidence.get("effective_warning"),
            "expected_effective_hard": evidence.get("effective_hard"),
            "expected_remaining_capacity": evidence.get("remaining_capacity"),
            "expected_overage": evidence.get("overage"),
        }
        for field, actual in expected_fields.items():
            if field in case and case[field] != actual:
                issues.append(f"{case_id}: {field} expected {case[field]}, got {actual}")
        error_fragment = str(case.get("expected_error_contains", ""))
        if error_fragment and not any(error_fragment in message for message in result.get("validation_errors", [])):
            issues.append(f"{case_id}: missing structured validation error containing {error_fragment!r}")
        if result.get("admission_scope") == "screenshot_batch" and result.get("batch_item_count") != case.get("batch_item_count"):
            issues.append(f"{case_id}: batch admission did not preserve batch_item_count")
        if "context_window_tokens" not in accounting or "response_reserve_tokens" not in accounting:
            issues.append(f"{case_id}: structured accounting omitted context or response reserve")
        if "status" not in evidence or "remaining_capacity" not in evidence:
            issues.append(f"{case_id}: structured evidence budget omitted status or remaining capacity")

    if statuses != {"pass", "warn", "reject"}:
        issues.append("resource-limit fixtures must exercise pass, warn, and reject")
    missing_cases = REQUIRED_BOUNDARY_CASES - seen
    if missing_cases:
        issues.append(f"resource-limit fixtures missing required cases: {', '.join(sorted(missing_cases))}")
    warnings.append(f"resource-limit summary: {len(seen)} context-aware boundary fixtures")
    return print_result("Resource-limit validation", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())

