#!/usr/bin/env python3
"""Validate the canonical liability/enforcement-outcomes registry."""

from __future__ import annotations

import argparse
import re
from datetime import date

from _kb import (
    duplicate_ids,
    ensure_list,
    id_set,
    normalize_jurisdiction_scope,
    parse_outcome_registry,
    parse_yaml_items,
    print_result,
    resolve_kb_root,
    scope_matches,
    source_file_exists,
)


ELIGIBILITY = {
    "eligible_monetary",
    "eligible_non_monetary",
    "ineligible_non_final",
    "ineligible_no_finding",
    "ineligible_source_only",
}
FINALITY_BLOCKERS = {"non_final", "pending", "unverified", "no_finding", "commitment"}
REQUIRED = {
    "id",
    "jurisdiction",
    "sub_jurisdiction",
    "authority",
    "matter_name",
    "date",
    "posture",
    "finality",
    "linked_norm_ids",
    "linked_patterns_or_practices",
    "legal_basis",
    "monetary_amount",
    "consumer_redress",
    "non_monetary_relief",
    "source_url",
    "local_staged_source_file",
    "source_pinpoint",
    "benchmark_eligibility",
    "comparability_notes",
    "limitations",
    "verified_date",
}


def valid_date(value: object, *, month_allowed: bool = False) -> bool:
    pattern = r"\d{4}-\d{2}(?:-\d{2})?" if month_allowed else r"\d{4}-\d{2}-\d{2}"
    return bool(re.fullmatch(pattern, str(value or "")))


def is_final(record: dict[str, object]) -> bool:
    value = str(record.get("finality", "")).lower()
    return not any(marker in value for marker in FINALITY_BLOCKERS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    registry_path = root / "taxonomy" / "enforcement_outcomes.yml"
    metadata, outcomes = parse_outcome_registry(registry_path)
    norms = parse_yaml_items(root / "taxonomy" / "norms.yml")
    norm_ids = id_set(norms)
    issues: list[str] = []
    warnings: list[str] = []

    if metadata.get("schema_version") != "1.1":
        issues.append("taxonomy/enforcement_outcomes.yml schema_version must be 1.1")
    if metadata.get("status") != "canonical":
        issues.append("taxonomy/enforcement_outcomes.yml status must be canonical")
    if not outcomes:
        issues.append("taxonomy/enforcement_outcomes.yml contains no outcomes")
    for duplicate in duplicate_ids(outcomes):
        issues.append(f"duplicate outcome id: {duplicate}")

    outcome_ids = id_set(outcomes)
    amount_types = set(ensure_list(metadata.get("amount_type_values")))
    default_availability = str(metadata.get("availability_default", ""))
    today = date.today().isoformat()
    norm_by_id = {str(item.get("id")): item for item in norms}
    norm_scopes: dict[str, tuple[str, str | None]] = {}
    for norm_id, norm in norm_by_id.items():
        try:
            scope = normalize_jurisdiction_scope(
                norm.get("jurisdiction", ""), norm.get("sub_jurisdiction")
            )
        except ValueError as exc:
            issues.append(f"{norm_id} has invalid jurisdiction scope: {exc}")
            continue
        if norm.get("jurisdiction") != scope[0] or norm.get("sub_jurisdiction") != scope[1]:
            issues.append(f"{norm_id} does not use canonical jurisdiction/sub_jurisdiction fields")
        norm_scopes[norm_id] = scope

    for record in outcomes:
        outcome_id = str(record.get("id", "<missing-id>"))
        missing = sorted(field for field in REQUIRED if field not in record)
        if missing:
            issues.append(f"{outcome_id} missing required fields: {', '.join(missing)}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", outcome_id):
            issues.append(f"invalid outcome id: {outcome_id}")
        if not valid_date(record.get("date"), month_allowed=True):
            issues.append(f"{outcome_id} has invalid outcome date")
        if not valid_date(record.get("verified_date")):
            issues.append(f"{outcome_id} has invalid verified_date")
        elif str(record.get("verified_date")) > today:
            issues.append(f"{outcome_id} verified_date is in the future")
        eligibility = str(record.get("benchmark_eligibility", ""))
        if eligibility not in ELIGIBILITY:
            issues.append(f"{outcome_id} has invalid benchmark_eligibility: {eligibility}")
        try:
            outcome_scope = normalize_jurisdiction_scope(
                record.get("jurisdiction", ""), record.get("sub_jurisdiction")
            )
        except ValueError as exc:
            outcome_scope = None
            issues.append(f"{outcome_id} has invalid jurisdiction scope: {exc}")
        else:
            if record.get("jurisdiction") != outcome_scope[0] or record.get("sub_jurisdiction") != outcome_scope[1]:
                issues.append(f"{outcome_id} does not use canonical jurisdiction/sub_jurisdiction fields")

        linked_norm_ids = ensure_list(record.get("linked_norm_ids"))
        linked_material_ids = {
            norm_id for norm_id in linked_norm_ids if norm_by_id.get(norm_id, {}).get("type") == "material"
        }
        for norm_id in linked_norm_ids:
            if norm_id not in norm_ids:
                issues.append(f"{outcome_id} links missing norm id {norm_id}")
                continue
            norm = norm_by_id[norm_id]
            if outcome_scope and not scope_matches(
                norm.get("jurisdiction", ""), norm.get("sub_jurisdiction"), outcome_scope
            ):
                issues.append(f"{outcome_id} links norm {norm_id} outside its canonical jurisdiction scope")
            if norm.get("type") == "procedural":
                companions = set(ensure_list(norm.get("companion_to_material_norm_ids")))
                if not companions & linked_material_ids:
                    issues.append(f"{outcome_id} uses procedural norm {norm_id} without a supported material norm")
        if linked_norm_ids and not linked_material_ids:
            issues.append(f"{outcome_id} must link at least one supported material norm before any procedural norm")
        if eligibility.startswith("eligible_") and not ensure_list(record.get("linked_norm_ids")):
            issues.append(f"{outcome_id} is eligible but has no linked norm id")

        source_url = str(record.get("source_url", ""))
        if not re.match(r"^https://", source_url):
            issues.append(f"{outcome_id} source_url must be HTTPS")
        if not str(record.get("source_pinpoint", "")).strip():
            issues.append(f"{outcome_id} has no source pinpoint")
        availability = str(record.get("availability", default_availability))
        if availability not in {"full_text", "press_release_only", "docket_only", "partial"}:
            issues.append(f"{outcome_id} has invalid source availability: {availability}")
        if availability == "press_release_only" and eligibility.startswith("eligible_"):
            issues.append(f"{outcome_id} is press_release_only and cannot be benchmark eligible")
        local_source = record.get("local_staged_source_file")
        if local_source and not source_file_exists(root, str(local_source)):
            issues.append(f"{outcome_id} local source does not resolve to a binary or verified capsule: {local_source}")

        monetary = record.get("monetary_amount")
        if monetary is not None and not isinstance(monetary, dict):
            issues.append(f"{outcome_id} monetary_amount must be an object or null")
        if isinstance(monetary, dict):
            amount = monetary.get("amount")
            if not isinstance(amount, (int, float)) or amount <= 0:
                issues.append(f"{outcome_id} monetary amount must be positive")
            if not re.fullmatch(r"[A-Z]{3}", str(monetary.get("currency", ""))):
                issues.append(f"{outcome_id} monetary currency must be a three-letter code")
            amount_type = str(monetary.get("amount_type", ""))
            if amount_type not in amount_types:
                issues.append(f"{outcome_id} has invalid or missing amount_type: {amount_type}")
            if not str(monetary.get("amount_basis", "")).strip():
                issues.append(f"{outcome_id} has no monetary amount_basis")
        if eligibility == "eligible_monetary":
            if not isinstance(monetary, dict):
                issues.append(f"{outcome_id} eligible_monetary requires a monetary object")
        if eligibility == "eligible_non_monetary":
            if monetary is not None:
                issues.append(f"{outcome_id} eligible_non_monetary must not carry a monetary amount")
        if eligibility.startswith("eligible_") and not is_final(record):
            issues.append(f"{outcome_id} benchmark-eligible outcome must have a final posture")
        if isinstance(monetary, dict) and monetary.get("amount_type") == "aggregate_multi_breach_fine":
            limits = f"{record.get('amount_basis', '')} {record.get('limitations', '')}".lower()
            nested_basis = str(monetary.get("amount_basis", "")).lower()
            if "aggregate" not in f"{limits} {nested_basis}" or "allocat" not in str(record.get("limitations", "")).lower():
                issues.append(f"{outcome_id} aggregate amount must state that it is not allocable")

    for norm in norms:
        norm_id = str(norm.get("id", "<missing-id>"))
        for outcome_id in ensure_list(norm.get("eligible_outcome_ids")):
            if outcome_id not in outcome_ids:
                issues.append(f"{norm_id} links missing outcome id {outcome_id}")
                continue
            outcome = next(item for item in outcomes if item.get("id") == outcome_id)
            if not str(outcome.get("benchmark_eligibility", "")).startswith("eligible_"):
                issues.append(f"{norm_id} links benchmark-ineligible outcome {outcome_id}")
            if norm_id not in ensure_list(outcome.get("linked_norm_ids")):
                issues.append(f"{norm_id} and {outcome_id} are not linked in both directions")
            try:
                outcome_scope = normalize_jurisdiction_scope(
                    outcome.get("jurisdiction", ""), outcome.get("sub_jurisdiction")
                )
            except ValueError:
                continue
            if not scope_matches(norm.get("jurisdiction", ""), norm.get("sub_jurisdiction"), outcome_scope):
                issues.append(f"{norm_id} links country outcome {outcome_id} outside its canonical scope")

    eligible = [o for o in outcomes if str(o.get("benchmark_eligibility", "")).startswith("eligible_")]
    monetary_eligible = [o for o in eligible if o.get("benchmark_eligibility") == "eligible_monetary"]
    warnings.append(
        f"registry summary: {len(outcomes)} records; {len(eligible)} eligible; "
        f"{len(monetary_eligible)} monetary and {len(eligible) - len(monetary_eligible)} non-monetary"
    )
    return print_result("Enforcement-outcomes validation", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())
