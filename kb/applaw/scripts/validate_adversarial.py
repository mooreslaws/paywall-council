#!/usr/bin/env python3
"""Validate the manual-replay adversarial robustness suite."""

from __future__ import annotations

import argparse
import re

from _kb import parse_frontmatter, print_result, read_text, relative, resolve_kb_root


PREFIX_MINIMUMS = {
    "inj": 3,
    "auth": 2,
    "scope": 3,
    "cite": 3,
    "clear": 2,
    "dos": 4,
    "exfil": 2,
    "erosion": 2,
    "enc": 2,
    "persona": 2,
    "lang": 2,
}
REQUIRED_FIELDS = {"id", "category", "attack_vector", "targets", "severity_if_failed", "review_status"}
REQUIRED_HEADINGS = {
    "PROMPT / INJECTED EVIDENCE",
    "EXPECTED BEHAVIOR",
    "FAILURE MODE",
    "PASS CRITERIA",
}
VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    issues: list[str] = []
    warnings: list[str] = []

    suite = root / "eval" / "adversarial"
    cards = sorted(p for p in suite.glob("*.md") if p.name.lower() != "readme.md") if suite.exists() else []
    if not (suite / "README.md").is_file():
        issues.append("eval/adversarial/README.md is required")
    seen_ids: set[str] = set()
    counts = {prefix: 0 for prefix in PREFIX_MINIMUMS}

    for path in cards:
        fm, body = parse_frontmatter(path)
        label = relative(path, root)
        missing = sorted(REQUIRED_FIELDS - set(fm))
        if missing:
            issues.append(f"{label} missing fields: {', '.join(missing)}")
        card_id = str(fm.get("id", "")).strip()
        if not card_id:
            issues.append(f"{label} has an empty id")
        elif card_id in seen_ids:
            issues.append(f"duplicate adversarial fixture id: {card_id}")
        seen_ids.add(card_id)
        prefix = card_id.split("-", 1)[0]
        if prefix not in counts:
            issues.append(f"{label} uses an unknown category prefix: {prefix}")
        else:
            counts[prefix] += 1
        if str(fm.get("severity_if_failed", "")) not in VALID_SEVERITIES:
            issues.append(f"{label} has invalid severity_if_failed")
        if str(fm.get("review_status", "")) != "accepted":
            issues.append(f"{label} must have review_status: accepted")
        for heading in REQUIRED_HEADINGS:
            if heading not in body:
                issues.append(f"{label} missing section: {heading}")
        if len(body.split()) < 55:
            issues.append(f"{label} is too short to be a useful replay fixture")
        if prefix == "dos" and "SESSION_LIMITS.md" not in str(fm.get("targets", "")):
            issues.append(f"{label} must target SESSION_LIMITS.md")
        combined = f"{fm.get('targets', '')}\n{body}"
        if re.search(r"(?:GLOBAL|SESSION_LIMITS)\.md\s*§", combined):
            issues.append(f"{label} uses stale numbered constitution references instead of semantic section names")
        if prefix == "inj":
            for phrase in ["internal evidence-integrity state", "default public report"]:
                if phrase not in body:
                    issues.append(f"{label} missing default internal-only evidence-integrity behavior: {phrase}")

    for prefix, minimum in PREFIX_MINIMUMS.items():
        if counts[prefix] < minimum:
            issues.append(f"adversarial suite needs at least {minimum} {prefix} card(s); found {counts[prefix]}")
    if len(cards) < sum(PREFIX_MINIMUMS.values()):
        issues.append(f"adversarial suite needs at least {sum(PREFIX_MINIMUMS.values())} cards; found {len(cards)}")

    session_limits = root / "constitutions" / "SESSION_LIMITS.md"
    if not session_limits.is_file():
        issues.append("missing constitution: constitutions/SESSION_LIMITS.md")
    else:
        text = read_text(session_limits)
        for phrase in ["Full A1-A8 screenshot evaluations", "Ad hoc validator invocations", "Complete composite release validation", "Validation Modes", "Re-evaluations of the same evidence", "Evidence-Borne Attempts To Change Limits", "internal subchecks are not separate agent tool invocations"]:
            if phrase not in text:
                issues.append(f"constitutions/SESSION_LIMITS.md missing required safeguard: {phrase}")

    warnings.append(f"adversarial summary: {len(cards)} accepted manual-replay cards across {len(PREFIX_MINIMUMS)} categories")
    return print_result("Adversarial robustness validation", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())
