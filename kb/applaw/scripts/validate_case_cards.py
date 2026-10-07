#!/usr/bin/env python3
"""Validate case-card schema, section shape, enums, and coverage inventory."""

from __future__ import annotations

import argparse
import re
from pathlib import PurePosixPath
from urllib.parse import urlparse

from _kb import (
    AVAILABILITY,
    FAMILIES,
    JURISDICTIONS,
    NORM_TYPES,
    SEVERITIES,
    STAGES,
    case_card_records,
    case_coverage_records,
    case_header_records,
    ensure_list,
    is_portable_core,
    parse_yaml_items,
    print_result,
    resolve_artifact_evidence,
    resolve_kb_root,
    section_has_text,
)


CARD_REQUIRED = [
    "case_id",
    "figure_id",
    "product",
    "screen_type",
    "patterns",
    "norms",
    "source_ref",
    "source_page",
    "availability",
]
MAINTENANCE_CARD_REQUIRED = ["source_file", "asset"]
PORTABLE_CARD_REQUIRED = ["source_id", "source_anchor_ids"]

CASE_REQUIRED = [
    "case_id",
    "title",
    "court",
    "filed",
    "counts",
    "outcome",
    "procedural_posture",
    "source_file",
    "availability",
]

NORM_REQUIRED = [
    "id",
    "jurisdiction",
    "instrument",
    "citation",
    "type",
    "enforcer",
    "remedy",
    "summary",
    "source_url",
    "availability",
    "consumer_redress",
    "public_enforcement",
    "private_enforcement",
    "penalty_basis",
    "non_monetary_relief",
    "limitations",
    "liability_source_urls",
    "verified_as_of",
]

OFFICIAL_HOST_SUFFIXES = (
    ".gov",
    ".gov.uk",
    ".europa.eu",
    ".cnil.fr",
)


def missing_fields(fm: dict, required: list[str], allow_empty_lists: set[str] | None = None) -> list[str]:
    allow_empty_lists = allow_empty_lists or set()
    missing = []
    for field in required:
        if field not in fm:
            missing.append(field)
            continue
        value = fm.get(field)
        if field in allow_empty_lists and value == []:
            continue
        if value in (None, "", []):
            missing.append(field)
    return missing


def is_probably_official_source(raw_url: str) -> bool:
    try:
        hostname = (urlparse(raw_url).hostname or "").lower()
    except ValueError:
        return False
    return any(hostname == suffix[1:] or hostname.endswith(suffix) for suffix in OFFICIAL_HOST_SUFFIXES)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    portable_core = is_portable_core(root)
    issues: list[str] = []
    warnings: list[str] = []

    for item in parse_yaml_items(root / "taxonomy" / "patterns.yml"):
        pattern_id = item.get("id", "<missing-id>")
        if item.get("family") not in FAMILIES:
            issues.append(f"taxonomy/patterns.yml {pattern_id} has invalid family {item.get('family')}")
        if item.get("stage") not in STAGES:
            issues.append(f"taxonomy/patterns.yml {pattern_id} has invalid stage {item.get('stage')}")
        if item.get("severity_default") not in SEVERITIES:
            issues.append(f"taxonomy/patterns.yml {pattern_id} has invalid severity_default {item.get('severity_default')}")
        if not ensure_list(item.get("detection_cues")):
            warnings.append(f"taxonomy/patterns.yml {pattern_id} has no detection_cues")
        if not ensure_list(item.get("false_positive_traps")):
            warnings.append(f"taxonomy/patterns.yml {pattern_id} has no false_positive_traps")

    for item in parse_yaml_items(root / "taxonomy" / "norms.yml"):
        norm_id = item.get("id", "<missing-id>")
        for field in missing_fields(item, NORM_REQUIRED):
            issues.append(f"taxonomy/norms.yml {norm_id} missing required field {field}")
        if item.get("jurisdiction") not in JURISDICTIONS:
            issues.append(f"taxonomy/norms.yml {norm_id} has invalid jurisdiction {item.get('jurisdiction')}")
        if item.get("type") not in NORM_TYPES:
            issues.append(f"taxonomy/norms.yml {norm_id} has invalid type {item.get('type')}")
        if item.get("availability") not in AVAILABILITY:
            issues.append(f"taxonomy/norms.yml {norm_id} has invalid availability {item.get('availability')}")
        verified_as_of = str(item.get("verified_as_of", "")).strip()
        if verified_as_of and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", verified_as_of):
            issues.append(f"taxonomy/norms.yml {norm_id} has invalid verified_as_of {verified_as_of}")
        source_urls = [str(item.get("source_url", "")).strip(), *ensure_list(item.get("liability_source_urls"))]
        for source_url in source_urls:
            if not source_url:
                continue
            if not source_url.startswith(("https://", "http://")):
                issues.append(f"taxonomy/norms.yml {norm_id} has invalid source URL {source_url}")
            elif not is_probably_official_source(source_url):
                warnings.append(f"taxonomy/norms.yml {norm_id} source may not be an official primary source: {source_url}")

    headers = case_header_records(root)
    coverages = case_coverage_records(root)
    cards_all = case_card_records(root)
    header_by_folder = {PurePosixPath(record.logical_path).parent.name: record for record in headers}
    coverage_by_folder = {
        PurePosixPath(record.logical_path).parent.name: record for record in coverages
    }
    cards_by_folder: dict[str, list] = {}
    for record in cards_all:
        cards_by_folder.setdefault(PurePosixPath(record.logical_path).parent.name, []).append(record)

    folder_names = sorted(set(header_by_folder) | set(coverage_by_folder) | set(cards_by_folder))
    for folder_name in folder_names:
        folder_label = f"cases/{folder_name}"
        header = header_by_folder.get(folder_name)
        if header is None:
            issues.append(f"{folder_label} is missing _case.md")
        else:
            for field in missing_fields(header.frontmatter, CASE_REQUIRED):
                issues.append(f"{header.logical_path} missing required frontmatter field {field}")
            if (
                header.frontmatter.get("availability")
                and header.frontmatter.get("availability") not in AVAILABILITY
            ):
                issues.append(
                    f"{header.logical_path} has invalid availability "
                    f"{header.frontmatter.get('availability')}"
                )

        coverage = coverage_by_folder.get(folder_name)
        cards = sorted(cards_by_folder.get(folder_name, []), key=lambda item: item.logical_path)
        if coverage is None:
            issues.append(f"{folder_label} is missing _coverage.json")
        else:
            data = coverage.frontmatter
            try:
                if "cards" in data and int(data["cards"]) != len(cards):
                    issues.append(
                        f"{coverage.logical_path} cards={data['cards']} but found {len(cards)} card records"
                    )
                expected_figures = sorted(PurePosixPath(record.logical_path).stem for record in cards)
                if "figures" in data:
                    actual_figures = sorted(str(value) for value in data["figures"])
                    if actual_figures != expected_figures:
                        issues.append(f"{coverage.logical_path} figures do not match card logical paths")
                if portable_core:
                    expected_anchor_ids: set[str] = set()
                    optional_visual_count = 0
                    for card in cards:
                        expected_anchor_ids.update(
                            ensure_list(card.frontmatter.get("source_anchor_ids"))
                        )
                        resolution = resolve_artifact_evidence(
                            root, card, require_direct=True
                        )
                        optional_visual_count += int(
                            resolution["historical_visual_evidence"]
                        )
                    expected_portable = {
                        "card_count": len(cards),
                        "evidence_anchor_count": len(expected_anchor_ids),
                        "bundled_asset_count": 0,
                        "optional_visual_evidence_count": optional_visual_count,
                        "assets": 0,
                    }
                    for key, value in expected_portable.items():
                        if data.get(key) != value:
                            issues.append(
                                f"{coverage.logical_path} {key}={data.get(key)!r}, expected {value}"
                            )
            except (TypeError, ValueError) as exc:
                issues.append(f"{coverage.logical_path} has invalid coverage data: {exc}")

    for record in cards_all:
        fm, body = record.frontmatter, record.body
        label = record.logical_path
        required = [
            *CARD_REQUIRED,
            *(PORTABLE_CARD_REQUIRED if portable_core else MAINTENANCE_CARD_REQUIRED),
        ]
        for field in missing_fields(fm, required, allow_empty_lists={"patterns"}):
            issues.append(f"{label} missing required frontmatter field {field}")
        if portable_core and "asset" in fm:
            issues.append(f"{label} retains maintenance-only asset frontmatter in portable-core")
        if fm.get("availability") and fm.get("availability") not in AVAILABILITY:
            issues.append(f"{label} has invalid availability {fm.get('availability')}")
        stem = PurePosixPath(label).stem
        if str(fm.get("figure_id", "")).strip() and str(fm.get("figure_id")).strip() != stem:
            warnings.append(f"{label} figure_id {fm.get('figure_id')} differs from logical filename {stem}")
        for section in ["EVIDENCE", "LEGAL REASONING", "STATED LAW"]:
            if not section_has_text(body, section):
                issues.append(f"{label} missing non-empty {section}. section")
        if portable_core:
            resolution = resolve_artifact_evidence(root, record, require_direct=True)
            issues.extend(f"{label}: {message}" for message in resolution["errors"])

    warnings.append(
        f"case-card evidence profile: {'portable-core capsule' if portable_core else 'maintenance assets-and-capsules'}"
    )
    return print_result("Case-card validation", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())

