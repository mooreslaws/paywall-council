#!/usr/bin/env python3
"""Evaluate context-aware post-ingestion evidence admission counters."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from _kb import resolve_kb_root


METRICS = ("ocr_characters", "evidence_tokens", "processing_seconds")
OCCUPIED_COMPONENTS = (
    "host_system_instruction_tokens",
    "project_instruction_tokens",
    "task_instruction_tokens",
    "existing_conversation_tokens",
)
TOKEN_COUNTERS = (
    "context_window_tokens",
    "occupied_input_tokens",
    *OCCUPIED_COMPONENTS,
    "cached_input_tokens",
    "retrieved_kb_tokens",
    "tool_output_reserve_tokens",
    "response_reserve_tokens",
    "safety_margin_tokens",
    "evidence_tokens",
)


def load_limits(root: Path) -> dict[str, Any]:
    path = root / "constitutions" / "RESOURCE_LIMITS.json"
    return json.loads(path.read_text(encoding="utf-8"))


def classify(value: float, warning: float, hard: float) -> str:
    if value > hard:
        return "reject"
    if value >= warning:
        return "warn"
    return "pass"


def _valid_non_negative(value: object, *, integer: bool) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    if not math.isfinite(float(value)) or value < 0:
        return False
    return not integer or float(value).is_integer()


def _display(value: object) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def _processing_metric(
    value: object,
    budget: dict[str, Any],
    *,
    invalid: bool = False,
) -> dict[str, Any]:
    status = "reject" if invalid else classify(float(value), budget["warning"], budget["hard"])
    return {
        "value": _display(value),
        "unit": budget["unit"],
        "warning": budget["warning"],
        "hard": budget["hard"],
        "status": status,
    }


def evaluate_admission(
    config: dict[str, Any],
    counters: dict[str, Any],
    *,
    admission_scope: str = "single_evidence",
    batch_item_count: object = None,
) -> dict[str, Any]:
    """Return a structured admission decision with non-overlapping token accounting."""
    errors: list[str] = []
    for name in TOKEN_COUNTERS:
        if name not in counters or counters[name] is None:
            errors.append(f"missing required counter: {name}")
        elif not _valid_non_negative(counters[name], integer=True):
            errors.append(f"{name} must be a non-negative finite integer")

    for name in ("ocr_characters", "processing_seconds"):
        if name not in counters or counters[name] is None:
            errors.append(f"missing required counter: {name}")
        elif not _valid_non_negative(counters[name], integer=(name == "ocr_characters")):
            kind = "integer" if name == "ocr_characters" else "number"
            errors.append(f"{name} must be a non-negative finite {kind}")

    if counters.get("occupied_input_includes_retrieved_kb") is True:
        errors.append("occupied_input_tokens must exclude retrieved_kb_tokens")
    if counters.get("occupied_input_includes_candidate_evidence") is True:
        errors.append("occupied_input_tokens must exclude candidate evidence tokens")
    if counters.get("evidence_token_count_exact") is False:
        errors.append("a byte-derived estimate cannot authorize admission; supply exact host evidence tokens")

    if admission_scope not in {"single_evidence", "screenshot_batch"}:
        errors.append(f"unsupported admission scope: {admission_scope}")
    if admission_scope == "screenshot_batch":
        if not _valid_non_negative(batch_item_count, integer=True) or int(batch_item_count or 0) < 1:
            errors.append("screenshot_batch admission requires a positive batch_item_count")

    valid_tokens = all(
        name in counters and _valid_non_negative(counters.get(name), integer=True)
        for name in TOKEN_COUNTERS
    )
    occupied_component_total: int | None = None
    reserved_non_evidence: int | None = None
    available_evidence: int | None = None
    effective_hard: int | None = None
    effective_warning: int | None = None
    remaining: int | None = None
    overage: int | None = None

    if valid_tokens:
        occupied_component_total = sum(int(counters[name]) for name in OCCUPIED_COMPONENTS)
        occupied = int(counters["occupied_input_tokens"])
        if occupied_component_total != occupied:
            errors.append(
                "occupied_input_tokens must equal the exact sum of its four declared components "
                f"({occupied_component_total}, not {occupied})"
            )
        cached = int(counters["cached_input_tokens"])
        if cached > occupied:
            errors.append("cached_input_tokens is a subset and cannot exceed occupied_input_tokens")

        reserved_non_evidence = (
            occupied
            + int(counters["retrieved_kb_tokens"])
            + int(counters["tool_output_reserve_tokens"])
            + int(counters["response_reserve_tokens"])
            + int(counters["safety_margin_tokens"])
        )
        context_window = int(counters["context_window_tokens"])
        if reserved_non_evidence > context_window:
            errors.append(
                "occupied input, retrieved KB, tool reserve, response reserve, and safety margin exceed the context window"
            )
        else:
            available_evidence = context_window - reserved_non_evidence
            absolute = config["budgets"]["evidence_tokens"]
            effective_hard = min(int(absolute["hard"]), available_evidence)
            effective_warning = min(
                int(absolute["warning"]),
                math.floor(effective_hard * int(absolute["warning"]) / int(absolute["hard"])),
            )
            evidence = int(counters["evidence_tokens"])
            remaining = max(effective_hard - evidence, 0)
            overage = max(evidence - effective_hard, 0)

    evidence_status = "reject"
    if effective_warning is not None and effective_hard is not None:
        evidence_status = classify(
            int(counters["evidence_tokens"]), effective_warning, effective_hard
        )

    metric_results: dict[str, dict[str, Any]] = {}
    ocr_valid = _valid_non_negative(counters.get("ocr_characters"), integer=True)
    time_valid = _valid_non_negative(counters.get("processing_seconds"), integer=False)
    metric_results["ocr_characters"] = _processing_metric(
        counters.get("ocr_characters"),
        config["budgets"]["ocr_characters"],
        invalid=not ocr_valid,
    )
    metric_results["evidence_tokens"] = {
        "value": _display(counters.get("evidence_tokens")),
        "unit": "tokens",
        "absolute_warning_ceiling": config["budgets"]["evidence_tokens"]["warning"],
        "absolute_hard_ceiling": config["budgets"]["evidence_tokens"]["hard"],
        "effective_warning": effective_warning,
        "effective_hard": effective_hard,
        "remaining_capacity": remaining,
        "overage": overage,
        "status": evidence_status,
    }
    metric_results["processing_seconds"] = _processing_metric(
        counters.get("processing_seconds"),
        config["budgets"]["processing_seconds"],
        invalid=not time_valid,
    )

    overall = "reject" if errors else "pass"
    if not errors:
        statuses = {metric["status"] for metric in metric_results.values()}
        overall = "reject" if "reject" in statuses else "warn" if "warn" in statuses else "pass"

    if errors:
        action = config["invalid_accounting_action"]
    elif overall == "reject":
        action = config["hard_limit_action"]
    elif overall == "warn":
        action = config["warning_action"]
    else:
        action = "Admit the evidence with all declared tool, response, and safety reserves preserved."

    return {
        "schema_version": config.get("schema_version"),
        "release_version": config.get("release_version"),
        "status": overall,
        "scope": config["scope"],
        "admission_scope": admission_scope,
        "batch_item_count": int(batch_item_count) if admission_scope == "screenshot_batch" and _valid_non_negative(batch_item_count, integer=True) else None,
        "accounting": {
            "context_window_tokens": _display(counters.get("context_window_tokens")),
            "occupied_input_tokens": _display(counters.get("occupied_input_tokens")),
            "occupied_input_components": {
                name: _display(counters.get(name)) for name in OCCUPIED_COMPONENTS
            },
            "occupied_input_component_total": occupied_component_total,
            "cached_input_tokens": _display(counters.get("cached_input_tokens")),
            "cached_input_accounting": "subset of occupied_input_tokens; still occupies context and is not subtracted",
            "retrieved_kb_tokens": _display(counters.get("retrieved_kb_tokens")),
            "tool_output_reserve_tokens": _display(counters.get("tool_output_reserve_tokens")),
            "response_reserve_tokens": _display(counters.get("response_reserve_tokens")),
            "safety_margin_tokens": _display(counters.get("safety_margin_tokens")),
            "reserved_non_evidence_tokens": reserved_non_evidence,
            "available_evidence_tokens": available_evidence,
            "formula": config["accounting_contract"]["available_evidence_formula"],
        },
        "metrics": metric_results,
        "validation_errors": errors,
        "action": action,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check post-ingestion context, OCR, token, and time counters. "
            "This does not inspect or limit uploaded files."
        )
    )
    parser.add_argument("--kb", default=None)
    parser.add_argument("--ocr-chars", type=int)
    evidence_group = parser.add_mutually_exclusive_group()
    evidence_group.add_argument("--evidence-tokens", type=int)
    evidence_group.add_argument("--batch-evidence-tokens", type=int)
    evidence_group.add_argument("--evidence-bytes", type=int)
    parser.add_argument("--batch-item-count", type=int)
    parser.add_argument("--elapsed-seconds", type=float)
    parser.add_argument("--context-window-tokens", type=int)
    parser.add_argument("--occupied-input-tokens", type=int)
    parser.add_argument("--host-system-instruction-tokens", type=int)
    parser.add_argument("--project-instruction-tokens", type=int)
    parser.add_argument("--task-instruction-tokens", type=int)
    parser.add_argument("--existing-conversation-tokens", type=int)
    parser.add_argument("--cached-input-tokens", type=int)
    parser.add_argument("--retrieved-kb-tokens", type=int)
    parser.add_argument("--tool-output-reserve-tokens", type=int)
    parser.add_argument("--response-reserve-tokens", type=int)
    parser.add_argument("--safety-margin-tokens", type=int)
    parser.add_argument("--occupied-input-includes-retrieved-kb", action="store_true")
    parser.add_argument("--occupied-input-includes-evidence", action="store_true")
    args = parser.parse_args()

    evidence_tokens = args.evidence_tokens
    exact_evidence_count = True
    admission_scope = "single_evidence"
    if args.batch_evidence_tokens is not None:
        evidence_tokens = args.batch_evidence_tokens
        admission_scope = "screenshot_batch"
    elif args.evidence_bytes is not None:
        evidence_tokens = math.ceil(args.evidence_bytes / 3)
        exact_evidence_count = False

    root = resolve_kb_root(args.kb)
    result = evaluate_admission(
        load_limits(root),
        {
            "ocr_characters": args.ocr_chars,
            "evidence_tokens": evidence_tokens,
            "processing_seconds": args.elapsed_seconds,
            "context_window_tokens": args.context_window_tokens,
            "occupied_input_tokens": args.occupied_input_tokens,
            "host_system_instruction_tokens": args.host_system_instruction_tokens,
            "project_instruction_tokens": args.project_instruction_tokens,
            "task_instruction_tokens": args.task_instruction_tokens,
            "existing_conversation_tokens": args.existing_conversation_tokens,
            "cached_input_tokens": args.cached_input_tokens,
            "retrieved_kb_tokens": args.retrieved_kb_tokens,
            "tool_output_reserve_tokens": args.tool_output_reserve_tokens,
            "response_reserve_tokens": args.response_reserve_tokens,
            "safety_margin_tokens": args.safety_margin_tokens,
            "occupied_input_includes_retrieved_kb": args.occupied_input_includes_retrieved_kb,
            "occupied_input_includes_candidate_evidence": args.occupied_input_includes_evidence,
            "evidence_token_count_exact": exact_evidence_count,
        },
        admission_scope=admission_scope,
        batch_item_count=args.batch_item_count,
    )
    result["token_count_source"] = (
        "host-supplied exact count" if exact_evidence_count else "UTF-8-byte estimate at 3 bytes per token; admission rejected"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False))
    return 2 if result["status"] == "reject" else 0


if __name__ == "__main__":
    raise SystemExit(main())

