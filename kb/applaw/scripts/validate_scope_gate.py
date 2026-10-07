#!/usr/bin/env python3
"""Very short check: is a mockup a checkout screen? Validates the A0 scope gate."""

from __future__ import annotations

import argparse

from _kb import parse_frontmatter, print_result, resolve_kb_root, resolve_skill_root


CHECKOUT_SIGNALS = (
    "price", "$", "€", "£", "/mo", "/month", "pay now", "place order",
    "add to cart", "checkout", "card number", "subscribe", "plan",
)


def is_checkout_mockup(evidence_text: str) -> bool:
    """Tiny heuristic mirroring references/scope-gate.md: any checkout
    signal (price, payment control, plan/subscribe language) means the
    mockup is in scope as checkout_or_pricing, not non_checkout."""
    text = evidence_text.lower()
    return any(signal in text for signal in CHECKOUT_SIGNALS)


CASES = [
    ("Hero headline, feature grid, trusted-by logos, blog cards, FAQ only", False),
    ("Pricing table: $39/month, cancel anytime, Get started button", True),
    ("Payment form with card number field and a Pay now button", True),
    ("Blog cards and a newsletter signup box, no payment control", False),
]

# The non_checkout short-circuit publishes a label, never the private score
# (report contract v3, "Prohibited Public Content").
REQUIRED_PHRASES = ["checkout_or_pricing", "non_checkout", "Skip A2-A6", "`very low`"]
FORBIDDEN_PHRASES = ["Score`: 1-10", "Risk band"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    skill = resolve_skill_root(root)
    issues: list[str] = []

    for evidence, expected in CASES:
        if is_checkout_mockup(evidence) != expected:
            issues.append(f"misclassified: {evidence!r} expected checkout={expected}")

    reference = skill / "references" / "scope-gate.md"
    if not reference.is_file():
        issues.append("missing references/scope-gate.md")
    else:
        text = reference.read_text(encoding="utf-8")
        for phrase in REQUIRED_PHRASES:
            if phrase not in text:
                issues.append(f"references/scope-gate.md missing required phrase: {phrase}")
        for phrase in FORBIDDEN_PHRASES:
            if phrase in text:
                issues.append(
                    f"references/scope-gate.md publishes a numeric score ({phrase}); "
                    "report contract v3 allows only the five-level label"
                )

    workflow = skill / "references" / "evaluation-workflow.md"
    if not workflow.is_file():
        issues.append("missing references/evaluation-workflow.md")
    elif "A0 Scope gate" not in workflow.read_text(encoding="utf-8"):
        issues.append("references/evaluation-workflow.md does not run A0 before A1")

    fixture_root = root / "eval" / "policy_fixtures"
    ids_needed = {"scope-gate-non-checkout", "scope-gate-checkout-screen"}
    ids_found = set()
    for path in fixture_root.glob("scope-gate-*.md") if fixture_root.exists() else []:
        fm, _ = parse_frontmatter(path)
        ids_found.add(str(fm.get("id", "")))
    for missing in sorted(ids_needed - ids_found):
        issues.append(f"missing scope-gate policy fixture: {missing}")

    return print_result("Scope-gate validation (is this mockup a checkout?)", issues)


if __name__ == "__main__":
    raise SystemExit(main())
