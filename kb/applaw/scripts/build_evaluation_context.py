#!/usr/bin/env python3
"""Build a deterministic, bounded AppLaw evaluation context slice."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from _kb import (
    artifact_semantic_digest,
    case_card_records,
    ensure_list,
    load_release_profile,
    load_source_capsules,
    parse_outcome_registry,
    parse_yaml_items,
    resolve_case_card,
    resolve_kb_root,
    source_anchor_index,
)
from route_norms import route_pattern


SCHEMA_VERSION = "1.0"
DEFAULT_MAX_CASES_PER_PATTERN = 3
DEFAULT_MAX_OUTCOMES_PER_NORM = 2
DEFAULT_MAX_BYTES = 160_000
STATIC_FINGERPRINT_PATHS = (
    "taxonomy/patterns.yml",
    "taxonomy/norms.yml",
    "taxonomy/jurisdiction_routes.yml",
    "taxonomy/enforcement_outcomes.yml",
    "sources/source_capsules.json",
)


def dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def kb_fingerprint_inputs(root: Path) -> list[tuple[str, bytes]]:
    """Return every semantic input that can affect a generated context slice."""
    inputs: list[tuple[str, bytes]] = []
    for relative in STATIC_FINGERPRINT_PATHS:
        path = root / relative
        inputs.append((f"file:{relative}", path.read_bytes()))
    for record in sorted(case_card_records(root), key=lambda item: item.logical_path):
        inputs.append(
            (
                f"case:{record.logical_path}",
                artifact_semantic_digest(record).encode("ascii"),
            )
        )
    return inputs


def kb_fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    for label, payload in kb_fingerprint_inputs(root):
        digest.update(label.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def compact_case(record: Any) -> dict[str, Any]:
    return {
        "logical_path": record.logical_path,
        "frontmatter": record.frontmatter,
        "body": record.body,
    }


def select_cases(
    root: Path,
    pattern_ids: list[str],
    selected_norm_ids: set[str],
    max_per_pattern: int,
    forced_case_refs: Iterable[str] = (),
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    records = list(case_card_records(root))
    selected: dict[str, Any] = {}
    counts: dict[str, dict[str, int]] = {}
    for case_ref in dedupe(forced_case_refs):
        record = resolve_case_card(root, case_ref)
        if record is None:
            raise ValueError(f"unresolved route case anchor: case:{case_ref}")
        selected.setdefault(record.logical_path, record)
    for pattern_id in pattern_ids:
        candidates = []
        for record in records:
            patterns = set(ensure_list(record.frontmatter.get("patterns")))
            norms = set(ensure_list(record.frontmatter.get("norms")))
            if pattern_id not in patterns:
                continue
            if not (norms & selected_norm_ids):
                continue
            candidates.append(record)
        candidates.sort(
            key=lambda record: (
                -len(set(ensure_list(record.frontmatter.get("norms"))) & selected_norm_ids),
                record.logical_path,
            )
        )
        included = candidates[:max_per_pattern]
        for record in included:
            selected.setdefault(record.logical_path, record)
        counts[pattern_id] = {
            "eligible": len(candidates),
            "included": len(included),
            "omitted": max(0, len(candidates) - len(included)),
        }
    return [compact_case(selected[path]) for path in sorted(selected)], counts


def select_outcomes(
    outcomes: dict[str, dict[str, Any]],
    norms: dict[str, dict[str, Any]],
    material_norm_ids: list[str],
    max_per_norm: int,
    forced_outcome_ids: Iterable[str] = (),
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    selected: dict[str, dict[str, Any]] = {}
    selected_for: dict[str, list[str]] = {}
    counts: dict[str, dict[str, int]] = {}
    forced = set(dedupe(forced_outcome_ids))
    for outcome_id in sorted(forced):
        outcome = outcomes.get(outcome_id)
        if outcome is None:
            raise ValueError(f"unresolved route outcome anchor: outcome:{outcome_id}")
        selected[outcome_id] = dict(outcome)
    for norm_id in material_norm_ids:
        norm = norms.get(norm_id, {})
        candidates = []
        for outcome_id in ensure_list(norm.get("eligible_outcome_ids")):
            outcome = outcomes.get(outcome_id)
            if not outcome:
                continue
            if not str(outcome.get("benchmark_eligibility", "")).startswith("eligible"):
                continue
            candidates.append(outcome)
        candidates.sort(key=lambda item: (str(item.get("date", "")), str(item.get("id", ""))), reverse=True)
        included = candidates[:max_per_norm]
        for outcome in included:
            outcome_id = str(outcome.get("id", ""))
            selected.setdefault(outcome_id, dict(outcome))
            selected_for.setdefault(outcome_id, []).append(norm_id)
        counts[norm_id] = {
            "eligible": len(candidates),
            "included": len(included),
            "omitted": max(0, len(candidates) - len(included)),
        }
    result = []
    for outcome_id in sorted(selected):
        payload = dict(selected[outcome_id])
        payload["selected_for_norm_ids"] = sorted(selected_for.get(outcome_id, []))
        payload["selected_as_route_anchor"] = outcome_id in forced
        result.append(payload)
    return result, counts


def resolve_route_anchors(
    root: Path,
    anchor_ids: Iterable[str],
    norms: dict[str, dict[str, Any]],
    outcomes: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    """Resolve symbolic route anchors to the records emitted in the context slice."""
    resolved = {
        "anchor_ids": [],
        "norm_ids": [],
        "outcome_ids": [],
        "case_refs": [],
        "case_logical_paths": [],
    }
    for anchor in dedupe(anchor_ids):
        if ":" not in anchor:
            raise ValueError(f"malformed route source anchor: {anchor}")
        kind, record_id = anchor.split(":", 1)
        if kind == "norm":
            if record_id not in norms:
                raise ValueError(f"unresolved route norm anchor: {anchor}")
            resolved["norm_ids"].append(record_id)
        elif kind == "outcome":
            if record_id not in outcomes:
                raise ValueError(f"unresolved route outcome anchor: {anchor}")
            resolved["outcome_ids"].append(record_id)
        elif kind == "case":
            record = resolve_case_card(root, record_id)
            if record is None:
                raise ValueError(f"unresolved route case anchor: {anchor}")
            resolved["case_refs"].append(record_id)
            resolved["case_logical_paths"].append(record.logical_path)
        else:
            raise ValueError(f"unsupported route source-anchor kind: {kind}")
        resolved["anchor_ids"].append(anchor)
    return {key: dedupe(values) for key, values in resolved.items()}


def select_sources(root: Path, anchor_ids: list[str]) -> list[dict[str, Any]]:
    anchor_lookup = source_anchor_index(root)
    registry = load_source_capsules(root)
    source_lookup = {
        str(source.get("source_id", "")): source
        for source in registry.get("sources", [])
        if isinstance(source, dict)
    }
    selected_anchors: dict[str, list[dict[str, Any]]] = {}
    for anchor_id in sorted(set(anchor_ids)):
        resolved = anchor_lookup.get(anchor_id)
        if not resolved:
            continue
        source, anchor = resolved
        source_id = str(source.get("source_id", ""))
        selected_anchors.setdefault(source_id, []).append(anchor)
    sources: list[dict[str, Any]] = []
    for source_id in sorted(selected_anchors):
        source = source_lookup[source_id]
        sources.append(
            {
                "source_id": source_id,
                "title": source.get("title"),
                "authority": source.get("authority"),
                "jurisdiction": source.get("jurisdiction"),
                "procedural_posture": source.get("procedural_posture"),
                "official_url": source.get("official_url"),
                "verified_as_of": source.get("verified_as_of"),
                "limitations": source.get("limitations"),
                "portable_core_limitations": source.get("portable_core_limitations"),
                "original_document": source.get("original_document"),
                "anchors": selected_anchors[source_id],
            }
        )
    return sources


def serialize_with_size(payload: dict[str, Any]) -> bytes:
    payload["output_bytes"] = 0
    while True:
        encoded = (json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        size = len(encoded)
        if payload["output_bytes"] == size:
            return encoded
        payload["output_bytes"] = size


def build_context(
    root: Path,
    pattern_ids: list[str],
    jurisdictions: list[str],
    facts: list[str] | Mapping[str, Iterable[str]] | None,
    *,
    max_cases_per_pattern: int = DEFAULT_MAX_CASES_PER_PATTERN,
    max_outcomes_per_norm: int = DEFAULT_MAX_OUTCOMES_PER_NORM,
) -> dict[str, Any]:
    patterns = {str(item.get("id", "")): item for item in parse_yaml_items(root / "taxonomy" / "patterns.yml")}
    norms = {str(item.get("id", "")): item for item in parse_yaml_items(root / "taxonomy" / "norms.yml")}
    _, outcome_items = parse_outcome_registry(root / "taxonomy" / "enforcement_outcomes.yml")
    outcomes = {str(item.get("id", "")): item for item in outcome_items}
    requested_patterns = dedupe(pattern_ids)
    routes = [route_pattern(root, pattern_id, jurisdictions, facts) for pattern_id in requested_patterns]
    route_anchors = resolve_route_anchors(
        root,
        (
            anchor_id
            for route in routes
            for anchor_id in route.get("source_anchor_ids", [])
        ),
        norms,
        outcomes,
    )
    material_norm_ids = dedupe(
        norm_id for route in routes for norm_id in route.get("material_norm_ids", [])
    )
    procedural_norm_ids = dedupe(
        norm_id for route in routes for norm_id in route.get("procedural_norm_ids", [])
    )
    selected_norm_ids = set(material_norm_ids) | set(procedural_norm_ids)
    unselected_norm_anchors = set(route_anchors["norm_ids"]) - selected_norm_ids
    if unselected_norm_anchors:
        raise ValueError(
            "route norm anchors are not present in the selected norm set: "
            + ", ".join(sorted(unselected_norm_anchors))
        )
    cases, case_counts = select_cases(
        root,
        requested_patterns,
        selected_norm_ids,
        max_cases_per_pattern,
        route_anchors["case_refs"],
    )
    selected_outcomes, outcome_counts = select_outcomes(
        outcomes,
        norms,
        material_norm_ids,
        max_outcomes_per_norm,
        route_anchors["outcome_ids"],
    )
    anchor_ids = dedupe(
        anchor_id
        for case in cases
        for anchor_id in ensure_list(case["frontmatter"].get("source_anchor_ids"))
    )
    warnings: list[str] = []
    if not jurisdictions:
        warnings.append("No target jurisdiction was supplied; the slice intentionally contains no jurisdiction-specific norms.")
    for route in routes:
        warnings.extend(str(item) for item in route.get("fact_warnings", []))
        if route.get("classification") in {"conditional_candidate", "mixed"}:
            warnings.append(f"{route['pattern_id']}: factual or source gates remain conditional; no authority is selected.")
        if route.get("status") == "abstain":
            warnings.append(f"{route['pattern_id']}: routing requires abstention for the supplied scope and facts.")
    if any(item["omitted"] for item in case_counts.values()):
        warnings.append("Comparable cases were capped deterministically; inspect omission counts before requesting a broader slice.")
    if any(item["omitted"] for item in outcome_counts.values()):
        warnings.append("Eligible outcomes were capped deterministically; inspect omission counts before requesting a broader slice.")
    profile = load_release_profile(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "release_version": str(profile.get("release_version", "")),
        "kb_fingerprint": kb_fingerprint(root),
        "request": {
            "pattern_ids": requested_patterns,
            "jurisdictions": jurisdictions,
            "facts": facts,
            "max_cases_per_pattern": max_cases_per_pattern,
            "max_outcomes_per_norm": max_outcomes_per_norm,
        },
        "routes": routes,
        "route_anchor_coverage": route_anchors,
        "patterns": [patterns[pattern_id] for pattern_id in requested_patterns],
        "norms": [norms[norm_id] for norm_id in [*material_norm_ids, *procedural_norm_ids]],
        "outcomes": selected_outcomes,
        "cases": cases,
        "sources": select_sources(root, anchor_ids),
        "omissions": {
            "cases_by_pattern": case_counts,
            "outcomes_by_norm": outcome_counts,
        },
        "warnings": dedupe(warnings),
        "output_bytes": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb", default=None, help="KB root")
    parser.add_argument("--pattern", action="append", required=True, help="Candidate pattern id; repeat as needed")
    parser.add_argument("--jurisdiction", action="append", default=[], help="Explicit jurisdiction; repeat or comma-separate")
    parser.add_argument("--fact", action="append", default=None, help="Legacy confirmed factual-gate token; repeat as needed")
    parser.add_argument("--confirmed-fact", action="append", default=None, help="Confirmed exact factual-gate token")
    parser.add_argument("--rejected-fact", action="append", default=None, help="Explicitly rejected exact factual-gate token")
    parser.add_argument("--unknown-fact", action="append", default=None, help="Explicitly unknown exact factual-gate token")
    parser.add_argument("--max-cases-per-pattern", type=int, default=DEFAULT_MAX_CASES_PER_PATTERN)
    parser.add_argument("--max-outcomes-per-norm", type=int, default=DEFAULT_MAX_OUTCOMES_PER_NORM)
    parser.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    parser.add_argument("--output", default=None, help="Optional UTF-8 JSON output path")
    args = parser.parse_args()
    if not 0 <= args.max_cases_per_pattern <= 10:
        parser.error("--max-cases-per-pattern must be between 0 and 10")
    if not 0 <= args.max_outcomes_per_norm <= 10:
        parser.error("--max-outcomes-per-norm must be between 0 and 10")
    if not 10_000 <= args.max_bytes <= 1_000_000:
        parser.error("--max-bytes must be between 10000 and 1000000")
    try:
        root = resolve_kb_root(args.kb)
        jurisdictions = dedupe(
            part
            for value in args.jurisdiction
            for part in str(value).split(",")
            if part.strip()
        )
        structured_facts = None
        if any(
            value is not None
            for value in (args.fact, args.confirmed_fact, args.rejected_fact, args.unknown_fact)
        ):
            structured_facts = {
                "confirmed": [*(args.fact or []), *(args.confirmed_fact or [])],
                "rejected": args.rejected_fact or [],
                "unknown": args.unknown_fact or [],
            }
        payload = build_context(
            root,
            args.pattern,
            jurisdictions,
            structured_facts,
            max_cases_per_pattern=args.max_cases_per_pattern,
            max_outcomes_per_norm=args.max_outcomes_per_norm,
        )
        encoded = serialize_with_size(payload)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if len(encoded) > args.max_bytes:
        print(
            f"ERROR: context slice is {len(encoded)} bytes, above --max-bytes {args.max_bytes}; "
            "reduce pattern count or per-pattern/per-norm caps",
            file=sys.stderr,
        )
        return 3
    if args.output:
        Path(args.output).write_bytes(encoded)
    else:
        sys.stdout.buffer.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
