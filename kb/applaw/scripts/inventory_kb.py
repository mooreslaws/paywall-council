#!/usr/bin/env python3
"""Inventory the checkout-funnel compliance KB."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _kb import (
    benchmark_records,
    case_card_records,
    case_coverage_records,
    case_header_records,
    gold_records,
    is_portable_core,
    load_release_profile,
    load_source_capsules,
    parse_outcome_registry,
    parse_yaml_items,
    resolve_artifact_evidence,
    resolve_kb_root,
)


EXPECTED_DIRS = [
    "constitutions",
    "constitutions/patterns",
    "constitutions/jurisdictions",
    "taxonomy",
    "cases",
    "benchmarks/clean",
    "eval/report_samples",
    "eval/resource_limits",
    "eval/output_safety",
    "eval/adversarial_replays",
    "sources",
]
MAINTENANCE_EXPECTED_DIRS = ["assets"]


def count_pngs(path: Path) -> int:
    return len(list(path.glob("*.png"))) if path.exists() else 0


def count_json_rows(path: Path) -> int:
    if not path.is_file():
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data) if isinstance(data, list) else 0


def build_inventory(root: Path) -> dict:
    profile = load_release_profile(root)
    portable_core = is_portable_core(root)
    pattern_items = parse_yaml_items(root / "taxonomy" / "patterns.yml")
    norm_items = parse_yaml_items(root / "taxonomy" / "norms.yml")
    route_path = root / "taxonomy" / "jurisdiction_routes.yml"
    route_items = parse_yaml_items(route_path) if route_path.is_file() else []
    _, outcome_items = parse_outcome_registry(root / "taxonomy" / "enforcement_outcomes.yml")
    eligible_outcomes = [
        item for item in outcome_items if str(item.get("benchmark_eligibility", "")).startswith("eligible_")
    ]
    cards = case_card_records(root)
    source_registry = load_source_capsules(root)
    source_capsules = source_registry.get("sources", []) if isinstance(source_registry, dict) else []
    referenced_capsules = [item for item in source_capsules if isinstance(item, dict) and item.get("referenced") is True]
    provenance_only_capsules = [
        item
        for item in source_capsules
        if isinstance(item, dict) and item.get("referenced") is not True
    ]
    source_anchor_count = sum(
        len(item.get("anchors", []))
        for item in referenced_capsules
        if isinstance(item.get("anchors", []), list)
    )
    visual_evidence_summaries = sum(
        1
        for item in referenced_capsules
        for anchor in item.get("anchors", [])
        if isinstance(anchor, dict)
        and (anchor.get("historical_visual_evidence") is True or bool(anchor.get("asset_refs")))
        and bool(str(anchor.get("evidence_summary", "")).strip())
    )
    artifact_groups = {
        "case": case_card_records(root),
        "gold": gold_records(root),
        "benchmark": benchmark_records(root),
    }
    resolved_artifacts = {kind: 0 for kind in artifact_groups}
    unresolved_evidence_references = 0
    for kind, paths in artifact_groups.items():
        for record in paths:
            resolution = resolve_artifact_evidence(
                root, record, require_direct=portable_core
            )
            if resolution["errors"]:
                unresolved_evidence_references += 1
            else:
                resolved_artifacts[kind] += 1
    case_law_pdfs = list((root / "case_law").glob("*.pdf")) if (root / "case_law").exists() else []
    downloaded_pdfs = list((root / "downloaded_pdfs").glob("*.pdf")) if (root / "downloaded_pdfs").exists() else []
    bundled_evidence_files = (
        [path for path in (root / "assets").rglob("*") if path.is_file()]
        if (root / "assets").exists()
        else []
    )
    headers = case_header_records(root)
    coverages = case_coverage_records(root)
    cards_by_folder: dict[str, list] = {}
    for record in cards:
        folder_name = Path(record.logical_path).parent.name
        cards_by_folder.setdefault(folder_name, []).append(record)
    header_folders = {Path(record.logical_path).parent.name for record in headers}
    coverage_folders = {Path(record.logical_path).parent.name for record in coverages}
    case_rows = []
    for folder_name in sorted(set(cards_by_folder) | header_folders | coverage_folders):
        card_count = len(cards_by_folder.get(folder_name, []))
        case_rows.append(
            {
                "case_folder": folder_name,
                "cards": card_count,
                "assets": count_pngs(root / "assets" / folder_name),
                "has_case_header": folder_name in header_folders,
                "has_coverage": folder_name in coverage_folders,
            }
        )
    return {
        "kb_root": str(root),
        "patterns": len(pattern_items),
        "norms": len(norm_items),
        "jurisdiction_route_groups": len(route_items),
        "enforcement_outcomes": len(outcome_items),
        "eligible_enforcement_outcomes": len(eligible_outcomes),
        "case_folders": len(case_rows),
        "case_cards": len(cards),
        "assets_png": len(list((root / "assets").rglob("*.png"))) if (root / "assets").exists() else 0,
        "eval_gold": len(gold_records(root)),
        "report_samples": len(list((root / "eval" / "report_samples").glob("*.md"))) if (root / "eval" / "report_samples").exists() else 0,
        "report_validation_fixtures": count_json_rows(root / "eval" / "report_validation_cases.json"),
        "policy_fixtures": len(list((root / "eval" / "policy_fixtures").glob("*.md"))) if (root / "eval" / "policy_fixtures").exists() else 0,
        "adversarial_fixtures": len(
            [p for p in (root / "eval" / "adversarial").glob("*.md") if p.name.lower() != "readme.md"]
        )
        if (root / "eval" / "adversarial").exists()
        else 0,
        "resource_limit_fixtures": count_json_rows(root / "eval" / "resource_limits" / "cases.json"),
        "output_safety_fixtures": count_json_rows(root / "eval" / "output_safety" / "cases.json"),
        "adversarial_replay_pairs": count_json_rows(root / "eval" / "adversarial_replays" / "cases.json"),
        "benchmarks_clean": len(benchmark_records(root)),
        "source_capsules": len(source_capsules),
        "referenced_source_capsules": len(referenced_capsules),
        "provenance_only_source_capsules": len(provenance_only_capsules),
        "provenance_only_source_capsule_ids": sorted(
            str(item.get("source_id", "")) for item in provenance_only_capsules
        ),
        "source_anchors": source_anchor_count,
        "case_records_with_resolved_anchors": resolved_artifacts["case"],
        "gold_records_with_resolved_anchors": resolved_artifacts["gold"],
        "benchmarks_with_resolved_anchors": resolved_artifacts["benchmark"],
        "visual_evidence_summaries": visual_evidence_summaries,
        "unresolved_evidence_references": unresolved_evidence_references,
        "bundled_evidence_bytes": sum(path.stat().st_size for path in bundled_evidence_files),
        "profile": profile.get("profile", "maintenance"),
        "case_law_pdfs": len(case_law_pdfs),
        "case_law_pdf_bytes": sum(path.stat().st_size for path in case_law_pdfs),
        "downloaded_pdfs": len(downloaded_pdfs),
        "downloaded_pdf_bytes": sum(path.stat().st_size for path in downloaded_pdfs),
        "missing_expected_dirs": [
            d
            for d in [
                *EXPECTED_DIRS,
                *(["eval"] if portable_core else ["eval/gold", *MAINTENANCE_EXPECTED_DIRS]),
            ]
            if not (root / d).exists()
        ],
        "cases": case_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None, help="KB root; defaults to cwd or nearest parent with taxonomy/ and cases/")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    inventory = build_inventory(root)
    if args.json:
        print(json.dumps(inventory, indent=2, ensure_ascii=False))
        return 0

    print(f"KB root: {inventory['kb_root']}")
    print(f"patterns: {inventory['patterns']}")
    print(f"norms: {inventory['norms']}")
    print(f"jurisdiction route groups: {inventory['jurisdiction_route_groups']}")
    print(f"enforcement outcomes: {inventory['enforcement_outcomes']}")
    print(f"eligible enforcement outcomes: {inventory['eligible_enforcement_outcomes']}")
    print(f"case folders: {inventory['case_folders']}")
    print(f"case cards: {inventory['case_cards']}")
    print(f"assets png: {inventory['assets_png']}")
    print(f"eval gold: {inventory['eval_gold']}")
    print(f"report samples: {inventory['report_samples']}")
    print(f"report validation fixtures: {inventory['report_validation_fixtures']}")
    print(f"policy fixtures: {inventory['policy_fixtures']}")
    print(f"adversarial fixtures: {inventory['adversarial_fixtures']}")
    print(f"resource-limit fixtures: {inventory['resource_limit_fixtures']}")
    print(f"output-safety fixtures: {inventory['output_safety_fixtures']}")
    print(f"adversarial replay pairs: {inventory['adversarial_replay_pairs']}")
    print(f"clean benchmarks: {inventory['benchmarks_clean']}")
    print(f"source capsules: {inventory['source_capsules']}")
    print(f"referenced source capsules: {inventory['referenced_source_capsules']}")
    print(f"provenance-only source capsules: {inventory['provenance_only_source_capsules']}")
    print(f"source anchors: {inventory['source_anchors']}")
    print(f"evidence profile: {inventory['profile']}")
    print(f"case records with resolved anchors: {inventory['case_records_with_resolved_anchors']}")
    print(f"gold records with resolved anchors: {inventory['gold_records_with_resolved_anchors']}")
    print(f"benchmarks with resolved anchors: {inventory['benchmarks_with_resolved_anchors']}")
    print(f"visual evidence summaries: {inventory['visual_evidence_summaries']}")
    print(f"unresolved evidence references: {inventory['unresolved_evidence_references']}")
    print(f"bundled evidence bytes: {inventory['bundled_evidence_bytes']}")
    print(f"case_law PDFs: {inventory['case_law_pdfs']}")
    print(f"case_law PDF bytes: {inventory['case_law_pdf_bytes']}")
    if (root / "downloaded_pdfs").exists():
        print(f"downloaded PDFs: {inventory['downloaded_pdfs']}")
        print(f"downloaded PDF bytes: {inventory['downloaded_pdf_bytes']}")
    if inventory["missing_expected_dirs"]:
        print("missing expected dirs:")
        for item in inventory["missing_expected_dirs"]:
            print(f"- {item}")
    print("cases:")
    for row in inventory["cases"]:
        print(f"- {row['case_folder']}: cards={row['cards']} assets={row['assets']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
