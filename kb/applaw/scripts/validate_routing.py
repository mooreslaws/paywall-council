#!/usr/bin/env python3
"""Validate canonical jurisdiction routing, material-first gates, and no fallback."""

from __future__ import annotations

import argparse
import json
import re

from build_evaluation_context import (
    build_context,
    kb_fingerprint_inputs,
    serialize_with_size,
)
from _kb import (
    canonical_scope,
    case_card_records,
    case_card_exists,
    ensure_list,
    normalize_jurisdiction_scope,
    parse_outcome_registry,
    parse_yaml_items,
    print_result,
    resolve_kb_root,
    scope_matches,
)
from route_norms import (
    normalize_fact,
    normalize_targets,
    route_norm_candidates,
    route_pattern,
)


def result_key(result: dict) -> tuple[str, str | None]:
    return normalize_jurisdiction_scope(
        result.get("jurisdiction", ""), result.get("sub_jurisdiction")
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    fixture_path = root / "eval" / "routing_cases.json"
    issues: list[str] = []
    warnings: list[str] = []
    if not fixture_path.is_file():
        return print_result("Jurisdiction routing validation", ["eval/routing_cases.json is missing"], warnings)

    try:
        fixtures = json.loads(fixture_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return print_result("Jurisdiction routing validation", [f"eval/routing_cases.json is not valid JSON: {exc}"], warnings)
    if not isinstance(fixtures, list) or not fixtures:
        return print_result("Jurisdiction routing validation", ["eval/routing_cases.json must contain a non-empty list"], warnings)

    norms = {str(item.get("id")): item for item in parse_yaml_items(root / "taxonomy" / "norms.yml")}
    # Every routing fact has to carry an observable definition. The Examiner
    # is shown these tokens and decides whether each is established; before
    # taxonomy/factual_gates.yml existed it saw only the slugs and inferred
    # the meaning from the name, which on the first live run left an obvious
    # payment screen's billing fact unconfirmed, emptied the
    # established-authority list and cost two report regenerations. Without
    # this check a new route can quietly reintroduce an undefined fact.
    gate_path = root / "taxonomy" / "factual_gates.yml"
    defined_facts: set[str] = set()
    if not gate_path.is_file():
        issues.append("taxonomy/factual_gates.yml is missing")
    else:
        for gate in parse_yaml_items(gate_path):
            gate_id = normalize_fact(str(gate.get("id") or ""))
            if not gate_id:
                issues.append("taxonomy/factual_gates.yml has an entry without an id")
                continue
            if gate_id in defined_facts:
                issues.append(f"taxonomy/factual_gates.yml defines {gate_id} more than once")
            defined_facts.add(gate_id)
            for field in ("detect", "avoid"):
                if not "".join(str(v) for v in ensure_list(gate.get(field))).strip():
                    issues.append(f"factual gate {gate_id} has an empty {field}")
    routed_facts: set[str] = set()
    _, outcome_items = parse_outcome_registry(root / "taxonomy" / "enforcement_outcomes.yml")
    outcomes = {str(item.get("id")): item for item in outcome_items}
    routes = parse_yaml_items(root / "taxonomy" / "jurisdiction_routes.yml")
    for route_record in routes:
        route_id = str(route_record.get("id", "<missing-id>"))
        if "sub_jurisdiction" not in route_record:
            issues.append(f"{route_id} must declare nullable sub_jurisdiction")
            continue
        try:
            route_scope = normalize_jurisdiction_scope(
                route_record.get("jurisdiction", ""), route_record.get("sub_jurisdiction")
            )
        except ValueError as exc:
            issues.append(f"{route_id} has invalid jurisdiction scope: {exc}")
            continue
        if route_record.get("jurisdiction") != route_scope[0] or route_record.get("sub_jurisdiction") != route_scope[1]:
            issues.append(f"{route_id} must use canonical jurisdiction/sub_jurisdiction fields")

        required = {normalize_fact(value) for value in ensure_list(route_record.get("required_facts"))}
        disqualifying = {normalize_fact(value) for value in ensure_list(route_record.get("disqualifying_facts"))}
        overlap = sorted(required & disqualifying)
        if overlap:
            issues.append(f"{route_id} has facts that are both required and disqualifying: {overlap}")
        for fact in sorted(required | disqualifying):
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fact):
                issues.append(f"{route_id} has invalid factual-gate token: {fact}")
            routed_facts.add(fact)

        candidate_norms = ensure_list(route_record.get("candidate_norms"))
        for norm_id in candidate_norms:
            norm = norms.get(norm_id)
            if not norm:
                issues.append(f"{route_id} references missing norm candidate {norm_id}")
                continue
            if norm.get("type") != "material":
                issues.append(f"{route_id} maps procedural norm directly from a visual pattern: {norm_id}")
            if not scope_matches(norm.get("jurisdiction", ""), norm.get("sub_jurisdiction"), route_scope):
                issues.append(f"{route_id} norm candidate {norm_id} is outside its canonical scope")

        anchors = ensure_list(route_record.get("source_anchor_ids"))
        if required and not anchors:
            issues.append(f"{route_id} has factual gates but no local source_anchor_ids")
        for anchor in anchors:
            if ":" not in anchor:
                issues.append(f"{route_id} has malformed source anchor: {anchor}")
                continue
            kind, anchor_id = anchor.split(":", 1)
            if kind == "norm":
                norm = norms.get(anchor_id)
                if not norm:
                    issues.append(f"{route_id} references missing norm anchor {anchor_id}")
                elif not scope_matches(norm.get("jurisdiction", ""), norm.get("sub_jurisdiction"), route_scope):
                    issues.append(f"{route_id} norm anchor {anchor_id} is outside its canonical scope")
            elif kind == "outcome":
                outcome = outcomes.get(anchor_id)
                if not outcome:
                    issues.append(f"{route_id} references missing outcome anchor {anchor_id}")
                elif not scope_matches(
                    outcome.get("jurisdiction", ""), outcome.get("sub_jurisdiction"), route_scope
                ):
                    issues.append(f"{route_id} outcome anchor {anchor_id} is outside its canonical scope")
            elif kind == "case":
                if not case_card_exists(root, anchor_id):
                    issues.append(f"{route_id} references missing case-card anchor {anchor_id}")
            else:
                issues.append(f"{route_id} uses unsupported source-anchor kind {kind}")

    seen: set[str] = set()
    normalized_alias_results: dict[str, list[dict[str, str | None]]] = {}
    for fixture in fixtures:
        fixture_id = str(fixture.get("id", "")).strip()
        if not fixture_id:
            issues.append("routing fixture has no id")
            continue
        if fixture_id in seen:
            issues.append(f"duplicate routing fixture id: {fixture_id}")
        seen.add(fixture_id)
        targets = fixture.get("target_jurisdictions", [])
        expected_error = str(fixture.get("expected_error_contains", ""))
        try:
            scopes = normalize_targets(targets)
            if "candidate_norm_ids" in fixture:
                route = route_norm_candidates(root, fixture.get("candidate_norm_ids", []), targets)
            else:
                fact_input = fixture.get("facts") if "facts" in fixture else None
                if any(
                    field in fixture
                    for field in ("confirmed_facts", "rejected_facts", "unknown_facts")
                ):
                    fact_input = {
                        "confirmed": fixture.get("confirmed_facts", []),
                        "rejected": fixture.get("rejected_facts", []),
                        "unknown": fixture.get("unknown_facts", []),
                    }
                route = route_pattern(
                    root,
                    str(fixture.get("pattern_id", "")).strip(),
                    targets,
                    fact_input,
                )
        except Exception as exc:
            if expected_error and expected_error in str(exc):
                continue
            issues.append(f"{fixture_id} could not be routed: {exc}")
            continue
        if expected_error:
            issues.append(f"{fixture_id} expected an error containing {expected_error!r}, but routing succeeded")
            continue

        expected_targets = [canonical_scope(scope) for scope in scopes]
        if route.get("target_jurisdictions") != expected_targets:
            issues.append(
                f"{fixture_id} emitted non-canonical targets {route.get('target_jurisdictions')}; expected {expected_targets}"
            )
        alias_group = str(fixture.get("alias_group", ""))
        if alias_group:
            normalized_alias_results.setdefault(alias_group, []).append(expected_targets)

        for field in ("status", "classification"):
            expected_value = str(fixture.get(f"expected_{field}", "")).strip()
            if expected_value and route.get(field) != expected_value:
                issues.append(f"{fixture_id} expected {field} {expected_value}, found {route.get(field)}")

        expected_norms = {str(value) for value in fixture.get("expected_material_norms", [])}
        actual_norms = [str(value) for value in route.get("material_norm_ids", [])]
        if set(actual_norms) != expected_norms:
            issues.append(f"{fixture_id} expected material norms {sorted(expected_norms)}, found {actual_norms}")
        if len(actual_norms) != len(set(actual_norms)):
            issues.append(f"{fixture_id} returned duplicate material norm candidates")
        actual_supported = {
            norm_id
            for norm_id, classification in route.get(
                "material_norm_classifications", {}
            ).items()
            if classification == "supported_route"
        }
        if "expected_supported_material_norms" in fixture:
            expected_supported = {
                str(value) for value in fixture.get("expected_supported_material_norms", [])
            }
        else:
            expected_supported = actual_supported
        if expected_supported != actual_supported:
            issues.append(
                f"{fixture_id} expected supported material norms {sorted(expected_supported)}, found {sorted(actual_supported)}"
            )
        expected_warning = str(fixture.get("expected_fact_warning_contains", ""))
        if expected_warning and not any(
            expected_warning in str(warning)
            for warning in route.get("fact_warnings", [])
        ):
            issues.append(
                f"{fixture_id} expected a factual-gate warning containing {expected_warning!r}"
            )
        expected_procedural = {str(value) for value in fixture.get("expected_procedural_norms", [])}
        if expected_procedural and set(route.get("procedural_norm_ids", [])) != expected_procedural:
            issues.append(
                f"{fixture_id} expected procedural companions {sorted(expected_procedural)}, found {route.get('procedural_norm_ids', [])}"
            )
        if route.get("procedural_norm_ids") and not actual_norms:
            issues.append(f"{fixture_id} returned a procedural norm without a material norm")
        expected_invalid = {str(value) for value in fixture.get("expected_invalid_primary_procedural_norms", [])}
        if expected_invalid != set(route.get("invalid_primary_procedural_norm_ids", [])):
            issues.append(
                f"{fixture_id} expected invalid primary procedural norms {sorted(expected_invalid)}, found {route.get('invalid_primary_procedural_norm_ids', [])}"
            )
        expected_anchors = {str(value) for value in fixture.get("expected_source_anchor_ids", [])}
        if expected_anchors and set(route.get("source_anchor_ids", [])) != expected_anchors:
            issues.append(
                f"{fixture_id} expected source anchors {sorted(expected_anchors)}, found {route.get('source_anchor_ids', [])}"
            )
        if route.get("selected_material_norm_id") is not None:
            issues.append(f"{fixture_id} selected an authority from unordered candidates")

        actual_results = {result_key(result): result for result in route.get("jurisdiction_results", [])}
        if list(actual_results) != scopes:
            issues.append(f"{fixture_id} expected separate canonical results {scopes}, found {list(actual_results)}")
        aggregate_from_results = {
            str(norm_id)
            for result in actual_results.values()
            if result.get("status") == "candidates"
            for norm_id in result.get("material_norm_ids", [])
        }
        if aggregate_from_results != set(actual_norms):
            issues.append(f"{fixture_id} aggregate candidates do not match jurisdiction-specific results")
        result_statuses = {str(result.get("status", "")) for result in actual_results.values()}
        if len(result_statuses) > 1 and route.get("status") != "mixed":
            issues.append(f"{fixture_id} hid mixed jurisdiction outcomes")

        for scope, result in actual_results.items():
            if result.get("selected_material_norm_id") is not None:
                issues.append(f"{fixture_id} {scope} selected an authority from candidate order")
            if result.get("status") == "abstain" and result.get("material_norm_ids"):
                issues.append(f"{fixture_id} {scope} abstention returned material candidates")
            if result.get("status") == "abstain" and result.get("source_anchor_ids"):
                issues.append(f"{fixture_id} {scope} abstention retained route source anchors")
            for norm_id in result.get("material_norm_ids", []):
                norm = norms.get(str(norm_id), {})
                if norm.get("type") != "material":
                    issues.append(f"{fixture_id} returned non-material primary candidate {norm_id}")
                if not scope_matches(norm.get("jurisdiction", ""), norm.get("sub_jurisdiction"), scope):
                    issues.append(f"{fixture_id} used {norm_id} as an analogue outside {scope}")
            material_for_result = set(result.get("material_norm_ids", []))
            for norm_id in result.get("procedural_norm_ids", []):
                norm = norms.get(str(norm_id), {})
                companions = set(ensure_list(norm.get("companion_to_material_norm_ids")))
                if norm.get("type") != "procedural" or not companions & material_for_result:
                    issues.append(f"{fixture_id} returned unsupported procedural companion {norm_id}")

        for expected_result in fixture.get("expected_jurisdiction_results", []):
            try:
                scope = normalize_jurisdiction_scope(
                    expected_result.get("jurisdiction", ""), expected_result.get("sub_jurisdiction")
                )
            except ValueError as exc:
                issues.append(f"{fixture_id} has invalid expected result scope: {exc}")
                continue
            actual_result = actual_results.get(scope)
            if not actual_result:
                issues.append(f"{fixture_id} missing expected jurisdiction result {scope}")
                continue
            for field in ("status", "classification"):
                expected_value = str(expected_result.get(field, "")).strip()
                if expected_value and actual_result.get(field) != expected_value:
                    issues.append(
                        f"{fixture_id} {scope} expected {field} {expected_value}, found {actual_result.get(field)}"
                    )
            expected_result_norms = {
                str(value) for value in expected_result.get("expected_material_norms", [])
            }
            if expected_result_norms != set(actual_result.get("material_norm_ids", [])):
                issues.append(
                    f"{fixture_id} {scope} expected material norms {sorted(expected_result_norms)}, found {actual_result.get('material_norm_ids', [])}"
                )
            actual_result_supported = {
                norm_id
                for norm_id, classification in actual_result.get(
                    "material_norm_classifications", {}
                ).items()
                if classification == "supported_route"
            }
            if "expected_supported_material_norms" in expected_result:
                expected_result_supported = {
                    str(value)
                    for value in expected_result.get("expected_supported_material_norms", [])
                }
            else:
                expected_result_supported = actual_result_supported
            if expected_result_supported != actual_result_supported:
                issues.append(
                    f"{fixture_id} {scope} expected supported material norms {sorted(expected_result_supported)}, found {sorted(actual_result_supported)}"
                )

        if not scopes:
            if actual_norms:
                issues.append(f"{fixture_id} selected a norm without target jurisdiction")
            if "No target jurisdiction supplied" not in str(route.get("reason", "")):
                issues.append(f"{fixture_id} missing-jurisdiction route has the wrong abstention reason")

    for alias_group, outputs in normalized_alias_results.items():
        if len(outputs) < 2 or any(output != outputs[0] for output in outputs[1:]):
            issues.append(f"alias group {alias_group} did not normalize every documented alias identically")

    try:
        context_one = build_context(root, ["hidden-renewal"], ["US"], None)
        context_two = build_context(root, ["hidden-renewal"], ["US"], None)
        encoded_one = serialize_with_size(context_one)
        encoded_two = serialize_with_size(context_two)
        if encoded_one != encoded_two:
            issues.append("evaluation context builder is not deterministic for identical input")
        if not re.fullmatch(r"[0-9a-f]{64}", str(context_one.get("kb_fingerprint", ""))):
            issues.append("evaluation context builder did not emit a SHA-256 KB fingerprint")
        fingerprint_labels = {label for label, _payload in kb_fingerprint_inputs(root)}
        expected_case_labels = {
            f"case:{record.logical_path}" for record in case_card_records(root)
        }
        if not expected_case_labels or not expected_case_labels.issubset(fingerprint_labels):
            issues.append("evaluation context fingerprint omits logical case-card inputs")
        if context_one.get("request", {}).get("pattern_ids") != ["hidden-renewal"]:
            issues.append("evaluation context builder did not preserve the requested pattern ids")
        if not context_one.get("norms") or not context_one.get("cases"):
            issues.append("evaluation context builder omitted routed norms or comparable cases")
        if not context_one.get("outcomes") or not context_one.get("sources"):
            issues.append("evaluation context builder omitted eligible outcomes or source capsules")
        if len(encoded_one) > 160_000 or context_one.get("output_bytes") != len(encoded_one):
            issues.append("evaluation context builder did not enforce a correct bounded-size record")

        no_scope = build_context(root, ["hidden-renewal"], [], None)
        if any(no_scope.get(key) for key in ("norms", "outcomes", "cases", "sources")):
            issues.append("evaluation context builder supplied jurisdiction-specific authority without a scope")
        if no_scope.get("route_anchor_coverage", {}).get("anchor_ids"):
            issues.append("evaluation context builder retained route anchors without a scope")
        if not any("No target jurisdiction" in str(item) for item in no_scope.get("warnings", [])):
            issues.append("evaluation context builder omitted the missing-jurisdiction warning")

        price_facts = [
            "invitation-to-purchase",
            "recurring-or-total-price-less-prominent",
            "transactional-decision-materiality",
        ]
        anchored = build_context(root, ["daily-price-framing"], ["UK"], price_facts)
        coverage = anchored.get("route_anchor_coverage", {})
        expected_anchor_ids = {
            "norm:uk-dmcc-225",
            "norm:uk-dmcc-230",
            "outcome:uk-cma-aa-bsm-2026",
            "case:uk_aa_bsm/lesson-package-selection-40",
        }
        if set(coverage.get("anchor_ids", [])) != expected_anchor_ids:
            issues.append("evaluation context builder did not resolve every supported route anchor")
        if "cases/uk_aa_bsm/lesson-package-selection-40.md" not in {
            case.get("logical_path") for case in anchored.get("cases", [])
        }:
            issues.append("evaluation context builder omitted the exact route-anchored case card")
        anchored_outcomes = {outcome.get("id"): outcome for outcome in anchored.get("outcomes", [])}
        if not anchored_outcomes.get("uk-cma-aa-bsm-2026", {}).get("selected_as_route_anchor"):
            issues.append("evaluation context builder omitted the exact route-anchored outcome")
        if not anchored.get("sources"):
            issues.append("evaluation context builder omitted capsule evidence for its route-anchored case")

        corrective = build_context(
            root,
            ["hard-cancellation"],
            ["EU"],
            [
                "consumer-subscription",
                "post-contract-cancellation",
                "material-cancellation-obstruction",
                "transactional-decision-materiality",
            ],
        )
        corrective_outcomes = {
            outcome.get("id"): outcome for outcome in corrective.get("outcomes", [])
        }
        corrective_anchor = corrective_outcomes.get("eu-cpc-amazon-prime-commitment-2022", {})
        if (
            corrective_anchor.get("benchmark_eligibility") != "ineligible_no_finding"
            or corrective_anchor.get("selected_as_route_anchor") is not True
        ):
            issues.append("evaluation context builder lost the posture of a corrective route anchor")

        abstained = build_context(
            root,
            ["daily-price-framing"],
            ["UK"],
            [*price_facts, "full-charge-and-cadence-equally-prominent"],
        )
        if any(abstained.get(key) for key in ("norms", "outcomes", "cases", "sources")):
            issues.append("evaluation context builder leaked authority after a false-positive abstention")
        if abstained.get("route_anchor_coverage", {}).get("anchor_ids"):
            issues.append("evaluation context builder retained anchors after a false-positive abstention")
    except Exception as exc:
        issues.append(f"evaluation context builder smoke test failed: {exc}")

    warnings.append(
        f"routing summary: {len(fixtures)} fixtures; {len(seen)} unique ids; deterministic context slice checked"
    )
    if gate_path.is_file():
        for fact in sorted(routed_facts - defined_facts):
            issues.append(f"routing fact {fact} has no entry in taxonomy/factual_gates.yml")
        for fact in sorted(defined_facts - routed_facts):
            warnings.append(f"factual gate {fact} is defined but no route uses it")

    return print_result("Jurisdiction routing validation", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())
