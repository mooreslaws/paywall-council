#!/usr/bin/env python3
"""Validate hard references across taxonomy, case cards, assets, and sources."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _kb import (
    NORM_TYPES,
    RELEASE_PROFILE_FILENAME,
    artifact_semantic_aggregate,
    artifact_resolution_count,
    artifact_record_index,
    benchmark_records,
    case_card_exists,
    case_card_records,
    case_coverage_records,
    case_header_records,
    duplicate_ids,
    ensure_list,
    gold_records,
    id_set,
    load_release_profile,
    parse_yaml_items,
    print_result,
    relative,
    normalize_jurisdiction_scope,
    load_source_capsules,
    normalize_artifact_path,
    normalize_source_alias,
    repo_path_exists,
    resolve_artifact_evidence,
    resolve_kb_root,
    scope_matches,
    source_file_exists,
)


PROHIBITED_BINARY_SUFFIXES = {
    ".bmp", ".gif", ".jpeg", ".jpg", ".pdf", ".png", ".tif", ".tiff", ".webp"
}
TEXT_SUFFIXES = {".json", ".md", ".py", ".txt", ".yaml", ".yml"}
PREDECESSOR_VERSION = ".".join(("0", "4", "0"))


def package_totals(root: Path) -> tuple[int, int]:
    files = [path for path in root.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt"]
    return len(files), sum(path.stat().st_size for path in files)


def validate_release_profile(
    root: Path, issues: list[str], warnings: list[str], *, require_pdf_free: bool
) -> bool:
    profile = load_release_profile(root)
    portable = profile.get("profile") == "portable-core"
    if require_pdf_free and not portable:
        issues.append(f"complete release validation requires {RELEASE_PROFILE_FILENAME} profile portable-core")
    if not portable:
        warnings.append("release profile: maintenance; canonical visual assets remain required")
        return False

    expected = {
        "schema_version": "1.0",
        "artifact_storage": "compact-json-v1",
        "skill_layout": "skill-root-v1",
        "installer_file_limit": 199,
        "target_file_budget": 150,
        "profile": "portable-core",
        "bundled_visual_assets": False,
        "evidence_mode": "capsule",
        "optional_evidence_pack_required": False,
        "pdf_count": 0,
        "bundled_image_count": 0,
        "semantic_digest_algorithm": "sha256",
        "semantic_normalization": "artifact-record-v1",
        "semantic_parity_verified": True,
        "checksum_manifest_excluded_from_package_totals": True,
    }
    for key, value in expected.items():
        if profile.get(key) != value:
            issues.append(f"{RELEASE_PROFILE_FILENAME} {key} must be {value!r}")
    try:
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        package = {}
        issues.append(f"cannot read package.json for release-profile validation: {exc}")
    registry = load_source_capsules(root)
    release_versions = {
        str(profile.get("release_version", "")),
        str(package.get("version", "")),
        str(registry.get("release_version", "")),
    }
    if len(release_versions) != 1 or "" in release_versions:
        issues.append("release profile, package, and source-capsule versions must match")

    case_cards = case_card_records(root)
    case_records = [
        *case_header_records(root),
        *case_coverage_records(root),
        *case_cards,
    ]
    gold = gold_records(root)
    benchmarks = benchmark_records(root)
    try:
        case_index = json.loads((root / "cases" / "index.json").read_text(encoding="utf-8"))
        gold_registry = json.loads((root / "eval" / "gold.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        case_index = {}
        gold_registry = {}
        issues.append(f"cannot read compact artifact metadata: {exc}")
    source_records = registry.get("sources", [])
    if not isinstance(source_records, list):
        source_records = []
    profile_semantics = {
        "benchmark_records_mapped": len(benchmarks),
        "case_bundle_count": len(case_index.get("cases", []))
        if isinstance(case_index.get("cases"), list)
        else 0,
        "case_records_mapped": len(case_cards),
        "case_semantic_record_count": len(case_records),
        "case_semantic_sha256": artifact_semantic_aggregate(case_cards),
        "gold_records_mapped": len(gold),
        "gold_semantic_sha256": artifact_semantic_aggregate(gold),
        "referenced_source_capsules": sum(
            1 for record in source_records if isinstance(record, dict) and record.get("referenced") is True
        ),
        "source_capsules": len(source_records),
    }
    for key, value in profile_semantics.items():
        if profile.get(key) != value:
            issues.append(f"{RELEASE_PROFILE_FILENAME} {key} is stale: {profile.get(key)!r} != {value!r}")
    if profile.get("gold_registry_summary") != gold_registry.get("summary"):
        issues.append(f"{RELEASE_PROFILE_FILENAME} gold_registry_summary is stale")

    if (root / "assets").exists():
        issues.append("portable-core package must not contain an assets directory")
    symlinks = sorted(relative(path, root) for path in root.rglob("*") if path.is_symlink())
    for rel in symlinks:
        issues.append(f"portable-core package contains a symlink: {rel}")
    prohibited = sorted(
        relative(path, root)
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in PROHIBITED_BINARY_SUFFIXES
    )
    for rel in prohibited:
        issues.append(f"portable-core package contains prohibited evidence binary: {rel}")

    file_count, byte_count = package_totals(root)
    if profile.get("package_file_count_before_checksum") != file_count:
        issues.append(
            f"{RELEASE_PROFILE_FILENAME} package file count is stale: "
            f"{profile.get('package_file_count_before_checksum')} != {file_count}"
        )
    if profile.get("package_bytes_before_checksum") != byte_count:
        issues.append(
            f"{RELEASE_PROFILE_FILENAME} package byte count is stale: "
            f"{profile.get('package_bytes_before_checksum')} != {byte_count}"
        )
    actual_total_files = file_count + int((root / "SHA256SUMS.txt").is_file())
    if actual_total_files >= 200:
        issues.append(f"portable package has {actual_total_files} files; 200 or more is prohibited")
    if actual_total_files > 150:
        issues.append(f"portable package has {actual_total_files} files; target budget is 150")
    if not (root / "SKILL.md").is_file():
        issues.append("portable package must place SKILL.md directly in the skill root")
    for prohibited_path in (
        root / "skills",
        root / ".claude",
        root / "AGENTS.md",
        root / "CLAUDE.md",
        root / "README.md",
        root / "architecture.txt",
        root / "KB_MAP.md",
        root / "PACKAGE_MANIFEST.md",
        root / "VALIDATION.md",
    ):
        if prohibited_path.exists():
            issues.append(f"portable package contains excluded path: {relative(prohibited_path, root)}")

    forbidden_versions = {
        ".".join(("0", "3", "0")),
        ".".join(("0", "3", "1")),
        ".".join(("0", "3", "2")),
        ".".join(("0", "3", "3")),
    }
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8-sig")
        found = sorted(value for value in forbidden_versions if value in text)
        if found:
            issues.append(f"portable package file identifies a forbidden release version {found}: {relative(path, root)}")
        if PREDECESSOR_VERSION in text:
            release_profile_reference = (
                path.name == RELEASE_PROFILE_FILENAME
                and profile.get("based_on_release") == PREDECESSOR_VERSION
                and text.count(PREDECESSOR_VERSION) == 1
            )
            if not release_profile_reference:
                issues.append(
                    f"portable package file retains a stale active predecessor declaration: {relative(path, root)}"
                )
    warnings.append(
        f"release profile: portable-core; {file_count} files and {byte_count} bytes before checksums; "
        "0 bundled images; 0 PDFs"
    )
    return True


def validate_source_capsules(
    root,
    issues: list[str],
    warnings: list[str],
    *,
    require_pdf_free: bool,
    portable_core: bool,
) -> None:
    registry = load_source_capsules(root)
    if not registry:
        issues.append("sources/source_capsules.json is missing or unreadable")
        return
    if registry.get("schema_version") != "1.0":
        issues.append("sources/source_capsules.json schema_version must be 1.0")
    if not portable_core:
        try:
            package = json.loads((root / "package.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            package = {}
            issues.append(f"cannot read package.json for source-capsule validation: {exc}")
        if registry.get("release_version") != package.get("version"):
            issues.append("maintenance source-capsule release_version must match package.json")
    policy = registry.get("policy", {})
    if not isinstance(policy, dict) or policy.get("portable_pdf_files_allowed") is not False:
        issues.append("source-capsule policy must prohibit PDFs in portable releases")
    records = registry.get("sources", [])
    if not isinstance(records, list) or not records:
        issues.append("sources/source_capsules.json contains no source records")
        return

    logical_index = artifact_record_index(root)
    duplicate_logical_paths = sorted(
        logical_path for logical_path, artifacts in logical_index.items() if len(artifacts) != 1
    )
    for logical_path in duplicate_logical_paths:
        issues.append(f"logical artifact resolves {len(logical_index[logical_path])} times: {logical_path}")

    source_ids: set[str] = set()
    all_anchor_ids: set[str] = set()
    linked_anchor_refs: list[tuple[str, str]] = []
    aliases: dict[str, str] = {}
    anchor_count = 0
    referenced_count = 0
    for record in records:
        if not isinstance(record, dict):
            issues.append("source capsule must be an object")
            continue
        source_id = str(record.get("source_id", ""))
        if not re.fullmatch(r"src-[0-9a-f]{16}", source_id):
            issues.append(f"invalid source capsule id: {source_id!r}")
        elif source_id in source_ids:
            issues.append(f"duplicate source capsule id: {source_id}")
        source_ids.add(source_id)
        original = record.get("original_document", {})
        if not isinstance(original, dict):
            original = {}
            issues.append(f"{source_id} original_document must be an object")
        filename = str(original.get("filename", ""))
        digest = str(original.get("sha256", ""))
        if not filename.lower().endswith(".pdf"):
            issues.append(f"{source_id} original filename must preserve its PDF provenance")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            issues.append(f"{source_id} has invalid original SHA-256")
        if not isinstance(original.get("bytes"), int) or int(original.get("bytes", 0)) <= 0:
            issues.append(f"{source_id} has invalid original byte count")
        if not isinstance(original.get("pages"), int) or int(original.get("pages", 0)) <= 0:
            issues.append(f"{source_id} has invalid original page count")
        if not str(record.get("title", "")).strip() or not str(record.get("procedural_posture", "")).strip():
            issues.append(f"{source_id} must declare title and procedural posture")
        for alias in [*record.get("aliases", []), filename]:
            normalized = normalize_source_alias(alias)
            if not normalized:
                continue
            prior = aliases.get(normalized)
            if prior and prior != source_id:
                issues.append(f"source alias {alias!r} maps to both {prior} and {source_id}")
            aliases[normalized] = source_id

        referenced = record.get("referenced") is True
        anchors = record.get("anchors", [])
        refs = record.get("referenced_by", [])
        extracts = record.get("page_extracts", [])
        if referenced:
            referenced_count += 1
            url = str(record.get("official_url", ""))
            if not url.startswith("https://"):
                issues.append(f"{source_id} referenced capsule requires an HTTPS official URL")
            if not isinstance(anchors, list) or not anchors:
                issues.append(f"{source_id} referenced capsule has no local anchors")
            if not isinstance(refs, list) or not refs:
                issues.append(f"{source_id} referenced capsule has no reverse references")
            for ref in refs if isinstance(refs, list) else []:
                try:
                    safe_ref = normalize_artifact_path(root, str(ref))
                except ValueError as exc:
                    issues.append(f"{source_id} has unsafe reverse reference {ref}: {exc}")
                    continue
                count = artifact_resolution_count(root, safe_ref)
                if count != 1:
                    issues.append(
                        f"{source_id} reverse reference resolves {count} times instead of once: {ref}"
                    )
        elif anchors:
            issues.append(f"{source_id} unreferenced capsule must not carry live anchors")

        extract_pages: set[int] = set()
        for extract in extracts if isinstance(extracts, list) else []:
            if not isinstance(extract, dict):
                issues.append(f"{source_id} page extract must be an object")
                continue
            page = extract.get("source_page")
            if not isinstance(page, int) or page <= 0:
                issues.append(f"{source_id} has invalid extracted source page: {page!r}")
                continue
            extract_pages.add(page)
            status = str(extract.get("status", ""))
            if status not in {"text_extracted", "image_or_no_extractable_text", "out_of_range"}:
                issues.append(f"{source_id} page {page} has invalid extraction status: {status}")
            if status == "text_extracted" and not str(extract.get("text", "")).strip():
                issues.append(f"{source_id} page {page} is marked text_extracted without text")
            if not re.fullmatch(r"[0-9a-f]{64}", str(extract.get("text_sha256", ""))):
                issues.append(f"{source_id} page {page} has invalid text digest")

        anchor_ids: set[str] = set()
        for anchor in anchors if isinstance(anchors, list) else []:
            if not isinstance(anchor, dict):
                issues.append(f"{source_id} anchor must be an object")
                continue
            anchor_id = str(anchor.get("anchor_id", ""))
            if not re.fullmatch(r"anc-[0-9a-f]{16}", anchor_id) or anchor_id in anchor_ids:
                issues.append(f"{source_id} has invalid or duplicate anchor id: {anchor_id!r}")
            if anchor_id in all_anchor_ids:
                issues.append(f"anchor id is duplicated across source capsules: {anchor_id}")
            anchor_ids.add(anchor_id)
            all_anchor_ids.add(anchor_id)
            page = anchor.get("source_page")
            if isinstance(page, int) and page not in extract_pages:
                issues.append(f"{source_id} {anchor_id} references source page {page} without a page extract")
            if not str(anchor.get("review_status", "")).strip():
                issues.append(f"{source_id} {anchor_id} has no review status")
            anchor_refs = ensure_list(anchor.get("referenced_by"))
            if not anchor_refs:
                issues.append(f"{source_id} {anchor_id} has no reverse references")
            for ref in anchor_refs:
                if ref not in ensure_list(refs):
                    issues.append(f"{source_id} {anchor_id} reverse reference is absent from its source record: {ref}")
                try:
                    safe_ref = normalize_artifact_path(root, ref)
                except ValueError as exc:
                    issues.append(f"{source_id} {anchor_id} has unsafe reverse reference {ref}: {exc}")
                    continue
                count = artifact_resolution_count(root, safe_ref)
                if count != 1:
                    issues.append(
                        f"{source_id} {anchor_id} reverse reference resolves {count} times "
                        f"instead of once: {ref}"
                    )

            asset_refs = ensure_list(anchor.get("asset_refs"))
            if portable_core and ("asset_refs" in anchor or asset_refs):
                issues.append(f"{source_id} {anchor_id} retains asset_refs in portable-core")
            if any(str(value).replace("\\", "/").startswith("assets/") for value in asset_refs):
                if portable_core:
                    issues.append(f"{source_id} {anchor_id} has a dangling local image path")
                else:
                    for value in asset_refs:
                        if not repo_path_exists(root, value):
                            issues.append(f"{source_id} {anchor_id} asset reference does not exist: {value}")

            evidence_summary = str(anchor.get("evidence_summary", "")).strip()
            historical_visual = anchor.get("historical_visual_evidence") is True or bool(asset_refs)
            if portable_core and historical_visual and not evidence_summary:
                issues.append(f"{source_id} {anchor_id} historical visual anchor has no semantic evidence summary")
            if portable_core and historical_visual and not str(anchor.get("visual_evidence_limitations", "")).strip():
                issues.append(f"{source_id} {anchor_id} historical visual anchor has no omitted-raster limitation")
            for linked_id in ensure_list(anchor.get("linked_case_anchor_ids")):
                linked_anchor_refs.append((anchor_id, linked_id))

            has_support = bool(evidence_summary or asset_refs or isinstance(page, int))
            if not has_support:
                issues.append(f"{source_id} {anchor_id} has no local evidence summary, asset, or pinpoint")
        anchor_count += len(anchors) if isinstance(anchors, list) else 0

    if require_pdf_free:
        pdf_files = sorted(path for path in root.rglob("*.pdf") if path.is_file())
        for path in pdf_files:
            issues.append(f"portable release contains prohibited PDF: {relative(path, root)}")
        if referenced_count and not aliases:
            issues.append("portable release has no source aliases")
    for anchor_id, linked_id in linked_anchor_refs:
        if linked_id not in all_anchor_ids:
            issues.append(f"{anchor_id} links to missing case-card evidence anchor {linked_id}")
    warnings.append(
        f"source-capsule summary: {len(records)} records; {referenced_count} referenced; "
        f"{len(records) - referenced_count} provenance-only; "
        f"{anchor_count} anchors; pdf-free release mode={'on' if require_pdf_free else 'off'}"
    )


def canonical_record_scope(item: dict, label: str, issues: list[str]) -> tuple[str, str | None] | None:
    if "sub_jurisdiction" not in item:
        issues.append(f"{label} must declare nullable sub_jurisdiction")
        return None
    try:
        scope = normalize_jurisdiction_scope(item.get("jurisdiction", ""), item.get("sub_jurisdiction"))
    except ValueError as exc:
        issues.append(f"{label} has invalid jurisdiction scope: {exc}")
        return None
    if item.get("jurisdiction") != scope[0] or item.get("sub_jurisdiction") != scope[1]:
        issues.append(
            f"{label} must use canonical jurisdiction={scope[0]!r} and sub_jurisdiction={scope[1]!r}"
        )
    return scope


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    parser.add_argument("--require-pdf-free", action="store_true")
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    issues: list[str] = []
    warnings: list[str] = []

    portable_core = validate_release_profile(
        root, issues, warnings, require_pdf_free=args.require_pdf_free
    )
    validate_source_capsules(
        root,
        issues,
        warnings,
        require_pdf_free=args.require_pdf_free,
        portable_core=portable_core,
    )

    patterns = parse_yaml_items(root / "taxonomy" / "patterns.yml")
    norms = parse_yaml_items(root / "taxonomy" / "norms.yml")
    pattern_ids = id_set(patterns)
    norm_ids = id_set(norms)
    norm_by_id = {str(item.get("id")): item for item in norms}

    norm_scopes: dict[str, tuple[str, str | None]] = {}
    for norm in norms:
        norm_id = str(norm.get("id", "<missing-id>"))
        scope = canonical_record_scope(norm, f"taxonomy/norms.yml {norm_id}", issues)
        if scope:
            norm_scopes[norm_id] = scope
        if norm.get("type") not in NORM_TYPES:
            issues.append(f"taxonomy/norms.yml {norm_id} has invalid norm type {norm.get('type')}")

    for norm in norms:
        norm_id = str(norm.get("id", "<missing-id>"))
        companion_ids = ensure_list(norm.get("companion_to_material_norm_ids"))
        if norm.get("type") == "material" and companion_ids:
            issues.append(f"taxonomy/norms.yml material norm {norm_id} cannot declare procedural companions")
        if norm.get("type") == "procedural":
            if not companion_ids:
                issues.append(f"taxonomy/norms.yml procedural norm {norm_id} has no supported material companion")
            for material_id in companion_ids:
                material = norm_by_id.get(material_id)
                if not material:
                    issues.append(f"taxonomy/norms.yml procedural norm {norm_id} references missing companion {material_id}")
                    continue
                if material.get("type") != "material":
                    issues.append(f"taxonomy/norms.yml {norm_id} companion {material_id} is not material")
                if norm_scopes.get(material_id) != norm_scopes.get(norm_id):
                    issues.append(f"taxonomy/norms.yml {norm_id} companion {material_id} is outside its jurisdiction scope")

    for duplicate in duplicate_ids(patterns):
        issues.append(f"duplicate pattern id: {duplicate}")
    for duplicate in duplicate_ids(norms):
        issues.append(f"duplicate norm id: {duplicate}")

    route_path = root / "taxonomy" / "jurisdiction_routes.yml"
    route_ids: set[str] = set()
    if not route_path.is_file():
        issues.append("taxonomy/jurisdiction_routes.yml is missing")
    for route in parse_yaml_items(route_path):
        route_id = str(route.get("id", "")).strip()
        if not route_id:
            issues.append("taxonomy/jurisdiction_routes.yml has a route without an id")
        elif route_id in route_ids:
            issues.append(f"duplicate jurisdiction route id: {route_id}")
        route_ids.add(route_id)
        route_scope = canonical_record_scope(
            route, f"taxonomy/jurisdiction_routes.yml {route_id}", issues
        )
        jurisdiction = route_scope[0] if route_scope else str(route.get("jurisdiction", "")).strip()
        pattern_refs = ensure_list(route.get("pattern_ids"))
        if not pattern_refs:
            issues.append(f"taxonomy/jurisdiction_routes.yml {route_id} has no pattern_ids")
        for pattern_id in pattern_refs:
            if pattern_id not in pattern_ids:
                issues.append(f"taxonomy/jurisdiction_routes.yml {route_id} references missing pattern id {pattern_id}")
        norm_refs = ensure_list(route.get("candidate_norms"))
        if not norm_refs:
            issues.append(f"taxonomy/jurisdiction_routes.yml {route_id} has no candidate_norms")
        for norm_id in norm_refs:
            norm = norm_by_id.get(norm_id)
            if not norm:
                issues.append(f"taxonomy/jurisdiction_routes.yml {route_id} references missing norm id {norm_id}")
            else:
                if route_scope and not scope_matches(
                    norm.get("jurisdiction", ""), norm.get("sub_jurisdiction"), route_scope
                ):
                    issues.append(
                        f"taxonomy/jurisdiction_routes.yml {route_id} mixes {route_scope} with {norm_id} scope {norm_scopes.get(norm_id)}"
                    )
                if norm.get("type") != "material":
                    issues.append(f"taxonomy/jurisdiction_routes.yml {route_id} maps procedural norm directly: {norm_id}")
        if not str(route.get("condition", "")).strip():
            warnings.append(f"taxonomy/jurisdiction_routes.yml {route_id} has no condition note")

    for item in patterns:
        pattern_id = item.get("id", "<missing-id>")
        for norm_id in ensure_list(item.get("maps_to_norms")):
            if norm_id not in norm_ids:
                issues.append(f"taxonomy/patterns.yml {pattern_id} maps to missing norm id {norm_id}")
            elif norm_by_id[norm_id].get("type") != "material":
                issues.append(
                    f"taxonomy/patterns.yml {pattern_id} maps procedural norm directly from a visual pattern: {norm_id}"
                )
        for ref in ensure_list(item.get("example_cases")):
            if not case_card_exists(root, ref):
                issues.append(f"taxonomy/patterns.yml {pattern_id} example case does not resolve: {ref}")

    for record in case_card_records(root):
        fm = record.frontmatter
        label = record.logical_path
        for pattern_id in ensure_list(fm.get("patterns")):
            if pattern_id not in pattern_ids:
                issues.append(f"{label} references missing pattern id {pattern_id}")
        card_norm_ids = ensure_list(fm.get("norms"))
        for norm_id in card_norm_ids:
            if norm_id not in norm_ids:
                issues.append(f"{label} references missing norm id {norm_id}")
        resolved_card_norms = [norm_by_id[norm_id] for norm_id in card_norm_ids if norm_id in norm_by_id]
        material_ids = {
            str(norm.get("id")) for norm in resolved_card_norms if norm.get("type") == "material"
        }
        if card_norm_ids and not material_ids:
            issues.append(f"{label} uses norms but has no supported material norm")
        card_scopes = {norm_scopes.get(str(norm.get("id"))) for norm in resolved_card_norms}
        card_scopes.discard(None)
        if len({scope[0] for scope in card_scopes}) > 1:
            issues.append(f"{label} mixes material or procedural norms from different jurisdictions")
        if len({scope[1] for scope in card_scopes if scope[1] is not None}) > 1:
            issues.append(f"{label} mixes norms from different country sub-jurisdictions")
        for norm in resolved_card_norms:
            if norm.get("type") != "procedural":
                continue
            norm_id = str(norm.get("id"))
            supported = set(ensure_list(norm.get("companion_to_material_norm_ids")))
            if not (supported & material_ids):
                issues.append(f"{label} uses procedural norm {norm_id} without a supported material companion")
        asset = fm.get("asset")
        if portable_core:
            if "asset" in fm:
                issues.append(f"{label} retains maintenance-only asset frontmatter in portable-core")
        else:
            if not asset:
                issues.append(f"{label} is missing asset")
            elif not repo_path_exists(root, str(asset)):
                issues.append(f"{label} asset does not exist: {asset}")
        source_file = fm.get("source_file")
        if not source_file:
            issues.append(f"{label} is missing source_file")
        elif not source_file_exists(root, str(source_file)):
            issues.append(f"{label} source_file does not resolve to a local binary or verified source capsule: {source_file}")
        if not fm.get("source_ref"):
            warnings.append(f"{label} has no source_ref")

    mapped_counts = {"case": 0, "gold": 0, "benchmark": 0}
    artifact_groups = {
        "case": case_card_records(root),
        "gold": gold_records(root),
        "benchmark": benchmark_records(root),
    }
    for kind, records in artifact_groups.items():
        for record in records:
            fm = record.frontmatter
            label = record.logical_path
            if portable_core and "asset" in fm:
                issues.append(f"{label} retains maintenance-only asset frontmatter in portable-core")
            resolution = resolve_artifact_evidence(
                root, record, require_direct=portable_core
            )
            if resolution["errors"]:
                issues.extend(f"{label}: {message}" for message in resolution["errors"])
            else:
                mapped_counts[kind] += 1
    warnings.append(
        "artifact evidence mappings: "
        f"{mapped_counts['case']} case; {mapped_counts['gold']} gold; "
        f"{mapped_counts['benchmark']} benchmark"
    )

    return print_result("Reference validation", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())
