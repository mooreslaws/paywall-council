#!/usr/bin/env python3
"""Validate clean benchmark cards."""

from __future__ import annotations

import argparse

from _kb import (
    JURISDICTIONS,
    RISK_BANDS,
    SCORE_BANDS,
    benchmark_paths,
    ensure_list,
    is_portable_core,
    parse_frontmatter,
    print_result,
    relative,
    repo_path_exists,
    resolve_artifact_evidence,
    resolve_kb_root,
    section_has_text,
)


REQUIRED = [
    "id",
    "product",
    "jurisdiction",
    "benchmark_type",
    "checkout_stage",
    "monetization_model",
    "expected_risk_band",
    "expected_score_band",
    "lawful_features",
    "false_positive_traps_covered",
    "evidence_source",
    "review_status",
]

BODY_SECTIONS = ["VISIBLE EVIDENCE", "WHY LOW RISK", "NOT A VIOLATION BECAUSE", "LIMITATIONS"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    parser.add_argument("--min-count", type=int, default=0, help="Fail if fewer benchmark cards exist")
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    portable_core = is_portable_core(root)
    issues: list[str] = []
    warnings: list[str] = []
    paths = benchmark_paths(root)
    if len(paths) < args.min_count:
        issues.append(f"benchmarks/clean has {len(paths)} card(s), below target {args.min_count}")
    if not paths:
        warnings.append("benchmarks/clean has no real benchmark cards yet; only templates/docs may exist")

    for path in paths:
        fm, body = parse_frontmatter(path)
        label = relative(path, root)
        for field in REQUIRED:
            if fm.get(field) in (None, "", []):
                issues.append(f"{label} missing required frontmatter field {field}")
        if portable_core:
            for field in ["source_id", "source_anchor_ids"]:
                if fm.get(field) in (None, "", []):
                    issues.append(f"{label} missing required portable frontmatter field {field}")
            if "asset" in fm:
                issues.append(f"{label} retains maintenance-only asset frontmatter in portable-core")
        if fm.get("jurisdiction") and fm.get("jurisdiction") not in JURISDICTIONS:
            issues.append(f"{label} has invalid jurisdiction {fm.get('jurisdiction')}")
        if fm.get("benchmark_type") and fm.get("benchmark_type") != "clean":
            issues.append(f"{label} benchmark_type should be clean")
        if fm.get("expected_risk_band") and fm.get("expected_risk_band") not in RISK_BANDS:
            issues.append(f"{label} has invalid expected_risk_band {fm.get('expected_risk_band')}")
        if fm.get("expected_score_band") and fm.get("expected_score_band") not in SCORE_BANDS:
            issues.append(f"{label} has invalid expected_score_band {fm.get('expected_score_band')}")
        if ensure_list(fm.get("lawful_features")) == []:
            issues.append(f"{label} lawful_features must list why the checkout is clean")
        if ensure_list(fm.get("false_positive_traps_covered")) == []:
            issues.append(f"{label} false_positive_traps_covered must list trap coverage")
        asset = fm.get("asset")
        if not portable_core and asset and str(asset).lower() != "none" and not repo_path_exists(root, str(asset)):
            issues.append(f"{label} asset does not exist: {asset}")
        for section in BODY_SECTIONS:
            if not section_has_text(body, section):
                issues.append(f"{label} missing non-empty {section}. section")
        resolution = resolve_artifact_evidence(
            root, label, fm, require_direct=portable_core
        )
        issues.extend(f"{label}: {message}" for message in resolution["errors"])

    warnings.append(
        f"benchmark evidence profile: {'portable-core capsule' if portable_core else 'maintenance assets-and-capsules'}"
    )
    return print_result("Clean benchmark validation", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())

