#!/usr/bin/env python3
"""Route pattern candidates through an explicit jurisdiction scope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from _kb import (
    canonical_scope,
    ensure_list,
    normalize_jurisdiction_scope,
    parse_yaml_items,
    resolve_kb_root,
    scope_label,
    scope_matches,
)


def normalize_scope(raw: str) -> tuple[str, str | None]:
    """Return a normalized (base jurisdiction, optional sub-jurisdiction)."""
    return normalize_jurisdiction_scope(raw)


def normalize_targets(values: Iterable[str] | None) -> list[tuple[str, str | None]]:
    scopes: list[tuple[str, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for raw in values or []:
        for part in str(raw).split(","):
            if not part.strip():
                continue
            scope = normalize_scope(part)
            if scope not in seen:
                seen.add(scope)
                scopes.append(scope)
    return scopes


def format_scope(scope: tuple[str, str | None]) -> str:
    return scope_label(scope)


def _route_index(root: Path) -> dict[tuple[str, str, str | None], list[dict[str, Any]]]:
    index: dict[tuple[str, str, str | None], list[dict[str, Any]]] = {}
    route_path = root / "taxonomy" / "jurisdiction_routes.yml"
    for route in parse_yaml_items(route_path):
        base, sub = normalize_jurisdiction_scope(
            route.get("jurisdiction", ""), route.get("sub_jurisdiction")
        )
        for pattern_id in ensure_list(route.get("pattern_ids")):
            index.setdefault((pattern_id, base, sub), []).append(route)
    return index


def _route_records(
    index: dict[tuple[str, str, str | None], list[dict[str, Any]]],
    pattern_id: str,
    scope: tuple[str, str | None],
) -> list[dict[str, Any]]:
    base, sub = scope
    records = list(index.get((pattern_id, base, sub), []))
    if sub:
        records.extend(index.get((pattern_id, base, None), []))
    return records


def normalize_fact(value: str) -> str:
    """Return an exact factual-gate token; prose and fuzzy aliases are invalid."""
    return str(value).strip()


def factual_gate_tokens(root: Path) -> set[str]:
    tokens: set[str] = set()
    for route in parse_yaml_items(root / "taxonomy" / "jurisdiction_routes.yml"):
        for field in ("required_facts", "disqualifying_facts"):
            tokens.update(normalize_fact(value) for value in ensure_list(route.get(field)))
    return {token for token in tokens if token}


def normalize_fact_states(
    root: Path,
    facts: Iterable[str] | Mapping[str, Iterable[str]] | None,
) -> dict[str, Any]:
    """Normalize legacy confirmed arrays or a structured three-state input."""
    allowed = factual_gate_tokens(root)
    raw_states: dict[str, Iterable[str]]
    if isinstance(facts, Mapping):
        raw_states = {
            state: facts.get(state, [])
            for state in ("confirmed", "rejected", "unknown")
        }
    else:
        raw_states = {"confirmed": facts or [], "rejected": [], "unknown": []}

    states: dict[str, set[str]] = {state: set() for state in raw_states}
    ignored = 0
    for state, raw_values in raw_states.items():
        values = [raw_values] if isinstance(raw_values, str) else raw_values
        for raw in values:
            token = normalize_fact(str(raw))
            if token in allowed:
                states[state].add(token)
            else:
                ignored += 1

    conflicts = (states["confirmed"] & states["rejected"]) | (
        states["confirmed"] & states["unknown"]
    ) | (states["rejected"] & states["unknown"])
    if conflicts:
        states["confirmed"] -= conflicts
        states["rejected"] -= conflicts
        states["unknown"] |= conflicts

    warnings: list[str] = []
    if ignored:
        warnings.append(
            "One or more unrecognized factual-gate values were ignored; they did not satisfy or reject any legal route."
        )
    if conflicts:
        warnings.append("Conflicting factual-gate states were treated as unknown.")
    return {
        "confirmed": states["confirmed"],
        "rejected": states["rejected"],
        "unknown": states["unknown"],
        "warnings": warnings,
    }


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def filter_norm_candidates(
    candidate_ids: Iterable[str],
    norms: dict[str, dict[str, Any]],
    scope: tuple[str, str | None],
) -> dict[str, list[str]]:
    """Filter arbitrary candidates without selecting from file order."""
    material: list[str] = []
    invalid_primary_procedural: list[str] = []
    unresolved: list[str] = []
    excluded: list[str] = []
    for norm_id in _dedupe(str(value) for value in candidate_ids):
        norm = norms.get(norm_id)
        if not norm:
            unresolved.append(norm_id)
            continue
        try:
            matches = scope_matches(
                norm.get("jurisdiction", ""), norm.get("sub_jurisdiction"), scope
            )
        except ValueError:
            unresolved.append(norm_id)
            continue
        if not matches:
            excluded.append(norm_id)
            continue
        if norm.get("type") == "material":
            material.append(norm_id)
        elif norm.get("type") == "procedural":
            invalid_primary_procedural.append(norm_id)
        else:
            unresolved.append(norm_id)
    return {
        "material_norm_ids": material,
        "invalid_primary_procedural_norm_ids": invalid_primary_procedural,
        "unresolved_norm_ids": unresolved,
        "excluded_norm_ids": excluded,
    }


def procedural_companions(
    norms: dict[str, dict[str, Any]],
    material_norm_ids: Iterable[str],
    scope: tuple[str, str | None],
) -> list[str]:
    """Add procedural norms only after a supported material candidate exists."""
    material = set(material_norm_ids)
    if not material:
        return []
    companions: list[str] = []
    for norm_id, norm in norms.items():
        if norm.get("type") != "procedural":
            continue
        if not scope_matches(norm.get("jurisdiction", ""), norm.get("sub_jurisdiction"), scope):
            continue
        supported_material = set(ensure_list(norm.get("companion_to_material_norm_ids")))
        if supported_material & material:
            companions.append(norm_id)
    return companions


def _scope_result(
    pattern_id: str,
    scope: tuple[str, str | None],
    mapped_norm_ids: list[str],
    norms: dict[str, dict[str, Any]],
    route_index: dict[tuple[str, str, str | None], list[dict[str, Any]]],
    fact_states: dict[str, Any],
) -> dict[str, Any]:
    scope_label = format_scope(scope)
    records = _route_records(route_index, pattern_id, scope)
    candidate_ids: list[str] = []
    route_group_ids: list[str] = []
    source_anchor_ids: list[str] = []
    missing_required_facts: list[str] = []
    rejected_required_facts: list[str] = []
    triggered_disqualifying_facts: list[str] = []
    candidate_classifications: dict[str, str] = {}
    confirmed = set(fact_states["confirmed"])
    rejected = set(fact_states["rejected"])

    def add_candidates(norm_ids: Iterable[str], classification: str) -> None:
        for norm_id in ensure_list(list(norm_ids)):
            candidate_ids.append(norm_id)
            if (
                candidate_classifications.get(norm_id) != "supported_route"
                or classification == "supported_route"
            ):
                candidate_classifications[norm_id] = classification

    if records:
        governed_norm_ids = {
            norm_id
            for record in records
            for norm_id in ensure_list(record.get("candidate_norms"))
        }
        # A route record governs only its declared candidates. Same-scope
        # baseline mappings outside that record remain conservative conditional
        # candidates; the governed narrow norm can never sneak back around its
        # factual gate through maps_to_norms.
        add_candidates(
            (norm_id for norm_id in mapped_norm_ids if norm_id not in governed_norm_ids),
            "conditional_candidate",
        )
        for record in records:
            route_id = str(record.get("id", ""))
            if route_id:
                route_group_ids.append(route_id)
            required = {normalize_fact(value) for value in ensure_list(record.get("required_facts"))}
            disqualifying = {normalize_fact(value) for value in ensure_list(record.get("disqualifying_facts"))}
            anchors = ensure_list(record.get("source_anchor_ids"))
            missing = sorted(required - confirmed)
            explicitly_rejected = sorted(required & rejected)
            triggered = sorted(disqualifying & confirmed)
            missing_required_facts.extend(missing)
            rejected_required_facts.extend(explicitly_rejected)
            triggered_disqualifying_facts.extend(triggered)
            if explicitly_rejected or triggered:
                continue
            classification = (
                "supported_route"
                if required and not missing and anchors
                else "conditional_candidate"
            )
            add_candidates(ensure_list(record.get("candidate_norms")), classification)
            source_anchor_ids.extend(anchors)
    else:
        add_candidates(mapped_norm_ids, "conditional_candidate")

    filtered = filter_norm_candidates(candidate_ids, norms, scope)
    material = filtered["material_norm_ids"]
    procedural = procedural_companions(norms, material, scope)
    unresolved = filtered["unresolved_norm_ids"]
    invalid_primary_procedural = filtered["invalid_primary_procedural_norm_ids"]
    material_classifications = {
        norm_id: candidate_classifications.get(norm_id, "conditional_candidate")
        for norm_id in material
    }

    if material:
        status = "candidates"
        classification = (
            "supported_route"
            if material_classifications
            and set(material_classifications.values()) == {"supported_route"}
            else "conditional_candidate"
        )
        if classification == "supported_route":
            reason = (
                f"{scope_label}: declared factual gates and local anchors support jurisdiction-matched material candidates; "
                "actor, transaction, contract-stage, implementation, and source-posture review still control final authority selection."
            )
        else:
            reason = (
                f"{scope_label}: jurisdiction-matched material candidates exist, but factual or source gates remain unresolved; "
                "candidate order does not select an authority."
            )
    else:
        status = "abstain"
        classification = "intentional_abstention"
        if triggered_disqualifying_facts:
            reason = (
                f"{scope_label}: a documented false-positive or exclusion fact is present "
                f"({', '.join(_dedupe(triggered_disqualifying_facts))}); no material norm is selected."
            )
        elif rejected_required_facts:
            reason = (
                f"{scope_label}: one or more required factual gates were explicitly rejected "
                f"({', '.join(_dedupe(rejected_required_facts))}); no material norm is selected."
            )
        else:
            reason = (
                f"{scope_label}: no jurisdiction-matched material norm candidate is mapped; "
                "do not fall back to another jurisdiction."
            )

    return {
        **canonical_scope(scope),
        "status": status,
        "classification": classification,
        "route_group_ids": _dedupe(route_group_ids),
        "material_norm_ids": material,
        "material_norm_classifications": material_classifications,
        "procedural_norm_ids": procedural,
        "invalid_primary_procedural_norm_ids": invalid_primary_procedural,
        "unresolved_norm_ids": _dedupe(unresolved),
        "source_anchor_ids": _dedupe(source_anchor_ids),
        "missing_required_facts": _dedupe(missing_required_facts),
        "rejected_required_facts": _dedupe(rejected_required_facts),
        "triggered_disqualifying_facts": _dedupe(triggered_disqualifying_facts),
        "selected_material_norm_id": None,
        "reason": reason,
    }


def route_pattern(
    root: Path,
    pattern_id: str,
    targets: Iterable[str] | None = None,
    facts: Iterable[str] | Mapping[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    patterns = {str(item.get("id")): item for item in parse_yaml_items(root / "taxonomy" / "patterns.yml")}
    norms = {str(item.get("id")): item for item in parse_yaml_items(root / "taxonomy" / "norms.yml")}
    if pattern_id not in patterns:
        raise ValueError(f"unknown pattern id: {pattern_id}")

    scopes = normalize_targets(targets)
    pattern = patterns[pattern_id]
    mapped_norm_ids = ensure_list(pattern.get("maps_to_norms"))
    fact_states = normalize_fact_states(root, facts)
    public_fact_states = {
        state: sorted(fact_states[state])
        for state in ("confirmed", "rejected", "unknown")
    }
    if not scopes:
        return {
            "pattern_id": pattern_id,
            "status": "abstain",
            "classification": "intentional_abstention",
            "target_jurisdictions": [],
            "facts": public_fact_states,
            "fact_warnings": fact_states["warnings"],
            "mapped_norm_ids": mapped_norm_ids,
            "route_group_ids": [],
            "material_norm_ids": [],
            "material_norm_classifications": {},
            "procedural_norm_ids": [],
            "invalid_primary_procedural_norm_ids": [],
            "unresolved_norm_ids": [],
            "source_anchor_ids": [],
            "jurisdiction_results": [],
            "selected_material_norm_id": None,
            "reason": "No target jurisdiction supplied; no jurisdiction-specific norm may be selected and no analogue fallback is permitted.",
        }

    route_index = _route_index(root)
    jurisdiction_results = [
        _scope_result(
            pattern_id,
            scope,
            mapped_norm_ids,
            norms,
            route_index,
            fact_states,
        )
        for scope in scopes
    ]
    statuses = {str(result["status"]) for result in jurisdiction_results}
    classifications = {str(result["classification"]) for result in jurisdiction_results}
    status = next(iter(statuses)) if len(statuses) == 1 else "mixed"
    classification = next(iter(classifications)) if len(classifications) == 1 else "mixed"
    material_classifications: dict[str, str] = {}
    for result in jurisdiction_results:
        for norm_id, norm_classification in result["material_norm_classifications"].items():
            if (
                material_classifications.get(norm_id) != "supported_route"
                or norm_classification == "supported_route"
            ):
                material_classifications[norm_id] = norm_classification

    return {
        "pattern_id": pattern_id,
        "status": status,
        "classification": classification,
        "target_jurisdictions": [canonical_scope(scope) for scope in scopes],
        "facts": public_fact_states,
        "fact_warnings": fact_states["warnings"],
        "mapped_norm_ids": mapped_norm_ids,
        "route_group_ids": _dedupe(
            route_id for result in jurisdiction_results for route_id in result["route_group_ids"]
        ),
        "material_norm_ids": _dedupe(
            norm_id for result in jurisdiction_results for norm_id in result["material_norm_ids"]
        ),
        "material_norm_classifications": material_classifications,
        "procedural_norm_ids": _dedupe(
            norm_id for result in jurisdiction_results for norm_id in result["procedural_norm_ids"]
        ),
        "invalid_primary_procedural_norm_ids": _dedupe(
            norm_id
            for result in jurisdiction_results
            for norm_id in result["invalid_primary_procedural_norm_ids"]
        ),
        "unresolved_norm_ids": _dedupe(
            norm_id for result in jurisdiction_results for norm_id in result["unresolved_norm_ids"]
        ),
        "source_anchor_ids": _dedupe(
            anchor_id for result in jurisdiction_results for anchor_id in result["source_anchor_ids"]
        ),
        "jurisdiction_results": jurisdiction_results,
        "selected_material_norm_id": None,
        "reason": " ".join(str(result["reason"]) for result in jurisdiction_results),
    }


def route_norm_candidates(
    root: Path,
    candidate_ids: Iterable[str],
    targets: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Filter an explicit candidate set for jurisdiction and material-first review."""
    norms = {str(item.get("id")): item for item in parse_yaml_items(root / "taxonomy" / "norms.yml")}
    scopes = normalize_targets(targets)
    candidate_list = _dedupe(str(value) for value in candidate_ids)
    if not scopes:
        return {
            "status": "abstain",
            "classification": "intentional_abstention",
            "target_jurisdictions": [],
            "candidate_norm_ids": candidate_list,
            "material_norm_ids": [],
            "procedural_norm_ids": [],
            "invalid_primary_procedural_norm_ids": [],
            "excluded_norm_ids": candidate_list,
            "jurisdiction_results": [],
            "selected_material_norm_id": None,
            "reason": "No target jurisdiction supplied; no jurisdiction-specific norm may be selected and no analogue fallback is permitted.",
        }

    results: list[dict[str, Any]] = []
    for scope in scopes:
        filtered = filter_norm_candidates(candidate_list, norms, scope)
        material = filtered["material_norm_ids"]
        result = {
            **canonical_scope(scope),
            "status": "candidates" if material else "abstain",
            "classification": "conditional_candidate" if material else "intentional_abstention",
            **filtered,
            "procedural_norm_ids": procedural_companions(norms, material, scope),
            "selected_material_norm_id": None,
            "reason": (
                f"{format_scope(scope)}: jurisdiction-matched material candidates remain subject to actor, transaction, factual-trigger, effective-date, availability, and source-anchor gates."
                if material
                else f"{format_scope(scope)}: no jurisdiction-matched material norm survives; no analogue fallback is permitted."
            ),
        }
        results.append(result)
    statuses = {result["status"] for result in results}
    classifications = {result["classification"] for result in results}
    return {
        "status": next(iter(statuses)) if len(statuses) == 1 else "mixed",
        "classification": next(iter(classifications)) if len(classifications) == 1 else "mixed",
        "target_jurisdictions": [canonical_scope(scope) for scope in scopes],
        "candidate_norm_ids": candidate_list,
        "material_norm_ids": _dedupe(
            norm_id for result in results for norm_id in result["material_norm_ids"]
        ),
        "procedural_norm_ids": _dedupe(
            norm_id for result in results for norm_id in result["procedural_norm_ids"]
        ),
        "invalid_primary_procedural_norm_ids": _dedupe(
            norm_id
            for result in results
            for norm_id in result["invalid_primary_procedural_norm_ids"]
        ),
        "excluded_norm_ids": _dedupe(
            norm_id for result in results for norm_id in result["excluded_norm_ids"]
        ),
        "jurisdiction_results": results,
        "selected_material_norm_id": None,
        "reason": " ".join(result["reason"] for result in results),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb", default=None, help="KB root")
    parser.add_argument("--pattern", action="append", default=[], help="Pattern id; repeat for multiple patterns")
    parser.add_argument("--candidate-norm", action="append", default=[], help="Explicit norm candidate id; repeat as needed")
    parser.add_argument("--jurisdiction", action="append", default=[], help="Explicit target jurisdiction; repeat or comma-separate")
    parser.add_argument("--fact", action="append", default=None, help="Legacy confirmed factual-gate token; repeat as needed")
    parser.add_argument("--confirmed-fact", action="append", default=None, help="Confirmed exact factual-gate token")
    parser.add_argument("--rejected-fact", action="append", default=None, help="Explicitly rejected exact factual-gate token")
    parser.add_argument("--unknown-fact", action="append", default=None, help="Explicitly unknown exact factual-gate token")
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    if bool(args.pattern) == bool(args.candidate_norm):
        parser.error("supply either --pattern or --candidate-norm, but not both")
    structured_facts = None
    if any(value is not None for value in (args.fact, args.confirmed_fact, args.rejected_fact, args.unknown_fact)):
        structured_facts = {
            "confirmed": [*(args.fact or []), *(args.confirmed_fact or [])],
            "rejected": args.rejected_fact or [],
            "unknown": args.unknown_fact or [],
        }
    try:
        if args.pattern:
            payload = {
                "kb_root": str(root),
                "routes": [
                    route_pattern(root, pattern_id, args.jurisdiction, structured_facts)
                    for pattern_id in args.pattern
                ],
            }
        else:
            payload = {
                "kb_root": str(root),
                "candidate_route": route_norm_candidates(root, args.candidate_norm, args.jurisdiction),
            }
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
