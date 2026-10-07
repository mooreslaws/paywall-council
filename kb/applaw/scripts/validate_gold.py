#!/usr/bin/env python3
"""Validate eval/gold cards."""

from __future__ import annotations

import argparse
import re

from _kb import (
    RISK_BANDS,
    SCORE_BANDS,
    ensure_list,
    gold_records,
    id_set,
    is_portable_core,
    normalize_jurisdiction_scope,
    parse_yaml_items,
    print_result,
    repo_path_exists,
    resolve_artifact_evidence,
    resolve_kb_root,
    section_has_text,
    source_file_exists,
)


REQUIRED = [
    "id",
    "case_id",
    "source_title",
    "screen_id",
    "screen_title",
    "jurisdiction",
    "source_kind",
    "source_file",
    "source_ref",
    "source_page",
    "expected_risk_band",
    "expected_score_band",
    "expected_patterns",
    "expected_norms",
    "complaint_paras",
    "review_status",
]
MAINTENANCE_REQUIRED = ["asset"]
PORTABLE_REQUIRED = ["source_id", "source_anchor_ids"]

BODY_SECTIONS = [
    "EXPECTED ANSWER",
    "EXPECTED FLAGS",
    "EXPECTED CITATIONS",
    "ACCEPTABLE VARIANTS",
    "REJECTION CRITERIA",
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    parser.add_argument("--strict-review", action="store_true", help="Fail unresolved review statuses")
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    portable_core = is_portable_core(root)
    issues: list[str] = []
    warnings: list[str] = []
    pattern_ids = id_set(parse_yaml_items(root / "taxonomy" / "patterns.yml"))
    norm_items = parse_yaml_items(root / "taxonomy" / "norms.yml")
    norm_ids = id_set(norm_items)
    norm_by_id = {str(item.get("id")): item for item in norm_items}

    seen_ids: set[str] = set()
    for record in gold_records(root):
        fm, body = record.frontmatter, record.body
        label = record.logical_path
        required = [*REQUIRED, *(PORTABLE_REQUIRED if portable_core else MAINTENANCE_REQUIRED)]
        for field in required:
            if fm.get(field) in (None, "", []):
                issues.append(f"{label} missing required frontmatter field {field}")
        gold_id = str(fm.get("id", "")).strip()
        if gold_id and gold_id in seen_ids:
            issues.append(f"duplicate gold id: {gold_id}")
        seen_ids.add(gold_id)
        if portable_core and "asset" in fm:
            issues.append(f"{label} retains maintenance-only asset frontmatter in portable-core")
        gold_scope: tuple[str, str | None] | None = None
        if fm.get("jurisdiction"):
            try:
                gold_scope = normalize_jurisdiction_scope(
                    fm.get("jurisdiction"), fm.get("sub_jurisdiction")
                )
            except ValueError as exc:
                issues.append(f"{label} has invalid jurisdiction scope: {exc}")
            else:
                if fm.get("jurisdiction") != gold_scope[0]:
                    issues.append(f"{label} jurisdiction must use canonical base value {gold_scope[0]}")
                if "sub_jurisdiction" in fm and fm.get("sub_jurisdiction") != gold_scope[1]:
                    issues.append(f"{label} sub_jurisdiction must use canonical ISO-style code {gold_scope[1]}")
        if fm.get("expected_risk_band") and fm.get("expected_risk_band") not in RISK_BANDS:
            issues.append(f"{label} has invalid expected_risk_band {fm.get('expected_risk_band')}")
        if fm.get("expected_score_band") and fm.get("expected_score_band") not in SCORE_BANDS:
            issues.append(f"{label} has invalid expected_score_band {fm.get('expected_score_band')}")
        for pattern_id in ensure_list(fm.get("expected_patterns")):
            if pattern_id not in pattern_ids:
                issues.append(f"{label} expected pattern id does not resolve: {pattern_id}")
        expected_norm_ids = ensure_list(fm.get("expected_norms"))
        material_norm_ids = {
            norm_id for norm_id in expected_norm_ids if norm_by_id.get(norm_id, {}).get("type") == "material"
        }
        if expected_norm_ids and not material_norm_ids:
            issues.append(f"{label} expected_norms must contain a supported material norm")
        for norm_id in expected_norm_ids:
            if norm_id not in norm_ids:
                issues.append(f"{label} expected norm id does not resolve: {norm_id}")
                continue
            norm = norm_by_id[norm_id]
            try:
                norm_scope = normalize_jurisdiction_scope(
                    norm.get("jurisdiction", ""), norm.get("sub_jurisdiction")
                )
            except ValueError as exc:
                issues.append(f"{label} expected norm {norm_id} has invalid scope: {exc}")
                continue
            if gold_scope and (norm_scope[0] != gold_scope[0] or (norm_scope[1] and norm_scope[1] != gold_scope[1])):
                issues.append(f"{label} expected norm {norm_id} is outside gold scope {gold_scope}")
            if norm.get("type") == "procedural":
                supported = set(ensure_list(norm.get("companion_to_material_norm_ids")))
                if not supported & material_norm_ids:
                    issues.append(f"{label} uses procedural norm {norm_id} without a supported material norm")
        if not portable_core and fm.get("asset") and not repo_path_exists(root, str(fm.get("asset"))):
            issues.append(f"{label} asset does not exist: {fm.get('asset')}")
        if fm.get("source_file") and not source_file_exists(root, str(fm.get("source_file"))):
            issues.append(f"{label} source_file does not resolve: {fm.get('source_file')}")
        if fm.get("review_status") == "needs_paragraph_anchor_review":
            message = f"{label} still needs paragraph-anchor review"
            if args.strict_review:
                issues.append(message)
            else:
                warnings.append(message)
        if fm.get("expected_score_band") and not re.match(r"^\d+-\d+$", str(fm.get("expected_score_band"))):
            issues.append(f"{label} expected_score_band should be a numeric range")
        for section in BODY_SECTIONS:
            if not section_has_text(body, section):
                issues.append(f"{label} missing non-empty {section}. section")
        if portable_core:
            resolution = resolve_artifact_evidence(root, record, require_direct=True)
            issues.extend(f"{label}: {message}" for message in resolution["errors"])

    warnings.append(
        f"gold evidence profile: {'portable-core capsule' if portable_core else 'maintenance assets-and-capsules'}"
    )
    return print_result("Gold validation", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())
