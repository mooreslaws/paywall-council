#!/usr/bin/env python3
"""Validate one explicitly supplied live report with the canonical report and safety rules."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import TextIO

from _kb import parse_yaml_items, resolve_kb_root
import validate_output_safety
import validate_report


MAX_INPUT_CHARACTERS = 2_000_000


def safe_report_issue(issue: str) -> str:
    value = issue
    for marker in ("contains non-bullet content:", "invalid F heading:", "invalid L heading:"):
        if marker in value:
            value = value.split(marker, 1)[0] + marker + " <redacted>"
    value = re.sub(r"[\r\n\t]+", " ", value).strip()
    return value[:400]


def safe_safety_issue(finding: str) -> str:
    if finding.startswith("internal taxonomy id:"):
        return "contains an internal taxonomy identifier"
    return f"contains prohibited {finding}"[:240]


def validate_live_text(
    text: str,
    root: Path,
    *,
    evidence_integrity_requested: bool = False,
    allowed_material_norm_ids: set[str] | None = None,
    conditional_material_norm_ids: set[str] | None = None,
    require_unsupported_jurisdiction_disclosure: bool = False,
) -> tuple[list[str], list[str]]:
    report_issues, report_warnings = validate_report.validate_report(
        Path("live-report.md"),
        root,
        evidence_integrity_requested=evidence_integrity_requested,
        text_override=text,
        label_override="live report",
        allowed_material_norm_ids=allowed_material_norm_ids,
        conditional_material_norm_ids=conditional_material_norm_ids,
        require_unsupported_jurisdiction_disclosure=require_unsupported_jurisdiction_disclosure,
    )
    internal_ids = validate_output_safety.load_internal_ids(root)
    safety_findings = validate_output_safety.scan_text(text, internal_ids)
    issues = [safe_report_issue(issue) for issue in report_issues]
    issues.extend(f"live report output safety {safe_safety_issue(item)}" for item in safety_findings)
    return issues, report_warnings


def input_mode_error(report_path: str | None, use_stdin: bool) -> str | None:
    if report_path and use_stdin:
        return "supply one report path or --stdin, not both"
    if not report_path and not use_stdin:
        return "an explicit report path or --stdin is required; live validation never falls back to samples"
    return None


def read_live_text(report_path: str | None, use_stdin: bool, stream: TextIO) -> tuple[str | None, str | None]:
    selection_error = input_mode_error(report_path, use_stdin)
    if selection_error:
        return None, selection_error
    if use_stdin:
        text = stream.read(MAX_INPUT_CHARACTERS + 1)
    else:
        path = Path(str(report_path))
        if not path.is_file():
            return None, "the supplied report path is not a readable file"
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            return None, "the supplied report could not be read as UTF-8 text"
    if len(text) > MAX_INPUT_CHARACTERS:
        return None, "the supplied report exceeds the live-validator input limit"
    if not text.strip():
        return None, "the supplied report text is empty"
    return text, None


def main(argv: list[str] | None = None, *, input_stream: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report_path", nargs="?", help="Exact live report file to validate")
    parser.add_argument("--stdin", action="store_true", help="Read the exact live report text from stdin")
    parser.add_argument("--kb", default=None, help="KB root")
    parser.add_argument(
        "--enforce-authority-slice",
        action="store_true",
        help="Require every primary Applicable norm to belong to the routed supported material set",
    )
    parser.add_argument(
        "--allowed-material-norm-id",
        action="append",
        default=[],
        help="Supported routed material norm id; repeat as needed",
    )
    parser.add_argument(
        "--conditional-material-norm-id",
        action="append",
        default=[],
        help="Material norm citable only with the conditional discipline (Medium confidence + 'conditional on ...'); repeat as needed",
    )
    parser.add_argument(
        "--require-unsupported-jurisdiction-disclosure",
        action="store_true",
        help="Require the standard Missing Context disclosure for an excluded unsupported market",
    )
    parser.add_argument(
        "--evidence-integrity-requested",
        action="store_true",
        help="Require the authorized Evidence integrity line because the initial operator prompt requested it",
    )
    args = parser.parse_args(argv)
    text, read_error = read_live_text(args.report_path, args.stdin, input_stream or sys.stdin)
    print("Live Report Contract v3 and output-safety validation")
    if read_error:
        print(f"FAIL: {read_error}")
        return 2
    try:
        root = resolve_kb_root(args.kb)
        allowed_material_norm_ids = None
        conditional_material_norm_ids: set[str] | None = None
        if args.enforce_authority_slice:
            allowed_material_norm_ids = set(args.allowed_material_norm_id)
            conditional_material_norm_ids = set(args.conditional_material_norm_id)
            material_ids = {
                str(norm.get("id"))
                for norm in parse_yaml_items(root / "taxonomy" / "norms.yml")
                if norm.get("type") == "material"
            }
            if not (allowed_material_norm_ids | conditional_material_norm_ids).issubset(material_ids):
                print("FAIL: the routed legal slice contains an invalid material-authority reference")
                return 2
        issues, _warnings = validate_live_text(
            str(text),
            root,
            evidence_integrity_requested=args.evidence_integrity_requested,
            allowed_material_norm_ids=allowed_material_norm_ids,
            conditional_material_norm_ids=conditional_material_norm_ids,
            require_unsupported_jurisdiction_disclosure=args.require_unsupported_jurisdiction_disclosure,
        )
    except Exception:
        print("FAIL: the live validator could not resolve or load the selected KB")
        return 2
    if issues:
        for issue in issues:
            print(f"FAIL: {issue}")
        return 1
    print("PASS: the exact supplied text satisfies Report Contract v3 and output safety")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
