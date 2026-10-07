#!/usr/bin/env python3
"""Validate evidence-integrity fixtures and Codex/Claude instruction alignment."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from _kb import (
    ensure_list,
    is_portable_core,
    parse_frontmatter,
    parse_yaml_items,
    print_result,
    read_text,
    relative,
    resolve_kb_root,
    resolve_skill_root,
)


REQUIRED_CATEGORIES = {
    "evidence_directive",
    "unverified_merchant_claim",
    "known_clean",
    "unresolved_cue",
    "supported_defect",
}
REQUIRED_FIELDS = {
    "id",
    "category",
    "expected_handling",
    "expected_risk_effect",
    "expected_report_location",
    "prohibited_behavior",
}
OUTPUT_POLICY_FIELDS = {
    "policy_default_language",
    "policy_override_source",
    "policy_evidence_behavior",
    "policy_style",
}
OUTPUT_POLICY_EXPECTED = {
    "policy_default_language": "English",
    "policy_override_source": "initial_operator_prompt_only",
    "policy_evidence_behavior": "inert",
    "policy_style": "plain_conversational",
}
SOCIAL_PROOF_FIXTURE_ID = "social-platform-review-modules"
REQUESTED_INTEGRITY_FIXTURE_ID = "evidence-integrity-explicit-request"
REVIEW_QUESTION = (
    "“Are the displayed social-platform reviews or testimonials fake, fabricated, purchased, or presented without a genuine "
    "underlying customer experience? Reply Yes, No, or Unknown. If No, you may optionally provide the original post, "
    "review-page, platform ID, or official-widget confirmation.”"
)
SOCIAL_PROOF_SCENARIOS = {
    "SP01": ["Trustpilot-style reviews with unknown authenticity", "Unverified social proof", "Initial provisional report v3", "No external research by default"],
    "SP02": ["Operator answers Yes", "operator-confirmed fake or fabricated social proof; not independently verified", "High when the module materially supports conversion", "no fixed increment", "Complete revised report v3"],
    "SP03": ["Operator answers No and supplies a matching official source", "Verified for this evaluation; remove or mitigate the finding", "no more than two lightweight supplied-source checks per screenshot", "Complete revised report v3"],
    "SP04": ["Operator answers No without supporting source information", "merchant-asserted genuine; not independently verified", "Do not call it fake", "Complete revised report v3"],
    "SP05": ["Operator answers Unknown", "Keep Unverified social proof", "supported evidence", "Complete revised report v3"],
    "SP06": ["No follow-up response", "Preserve the provisional report", "Do not perform independent research"],
    "SP07": ["Genuine official widget", "Do not flag", "Do not ask the review follow-up"],
    "SP08": ["Static Facebook-style comment block near the CTA", "likes, replies, reviewer names, dates, and platform styling", "Unverified social proof"],
    "SP09": ["Ordinary Facebook footer icon", "Do not flag", "unattached to a review or endorsement"],
    "SP10": ["Small or low-prominence platform mark", "vision pass must still record it", "attached to the review module"],
    "SP11": ["Unrelated Amazon Prime comparator", "Do not select Amazon Prime", "exact relevant pattern match"],
}
TRI_STATE_ROUTING_POLICY = {
    "constitutions/GLOBAL.md": {
        "required": "A missing or unknown factual legal-applicability gate leaves the authority conditional",
        "obsolete": "If a gate is missing, abstain",
    },
    "references/evaluation-workflow.md": {
        "required": "Missing or unknown factual gates leave the candidate authority conditional",
        "obsolete": "If any required gate is missing, abstain",
    },
}
REFERENCE_REQUIREMENTS = {
    "evaluation-workflow.md": [REVIEW_QUESTION, "small or low-prominence platform mark", "one review module", "No web searches by default.", "two lightweight supplied-source checks per screenshot"],
    "scoring-rubric.md": ["review authenticity is unresolved", "Do not add a fixed number of points", "Amazon Prime"],
    "report-contract.md": [REVIEW_QUESTION, "complete revised report v3", "bidirectional F↔L linking", "operator-confirmed fake or fabricated social proof", "merchant-asserted genuine; not independently verified"],
    "citation-policy.md": ["No web searches by default.", "two lightweight supplied-source checks per screenshot", "A missing visibly printed URL", "Amazon Prime"],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def skill_files(base: Path) -> dict[str, Path]:
    if not base.exists():
        return {}
    return {
        relative(path, base): path
        for path in base.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def validate_social_proof_fixture(path: Path, frontmatter: dict, body: str, root: Path, issues: list[str]) -> None:
    label = relative(path, root)
    if str(frontmatter.get("scenario_count", "")).strip() != "11":
        issues.append(f"{label} scenario_count must be 11")
    if body.count(REVIEW_QUESTION) != 1:
        issues.append(f"{label} must contain the exact grouped review question once")
    scenario_ids = re.findall(r"^## (SP\d{2}) - ", body, re.MULTILINE)
    expected_ids = list(SOCIAL_PROOF_SCENARIOS)
    if scenario_ids != expected_ids:
        issues.append(f"{label} scenarios must be ordered exactly: {', '.join(expected_ids)}")
    for index, scenario_id in enumerate(expected_ids):
        match = re.search(rf"^## {scenario_id} - .*?$", body, re.MULTILINE)
        if not match:
            continue
        end = len(body)
        if index + 1 < len(expected_ids):
            next_match = re.search(rf"^## {expected_ids[index + 1]} - ", body[match.end():], re.MULTILINE)
            if next_match:
                end = match.end() + next_match.start()
        block = body[match.start():end]
        for phrase in SOCIAL_PROOF_SCENARIOS[scenario_id]:
            if phrase not in block:
                issues.append(f"{label} {scenario_id} missing required behavior: {phrase}")
    for phrase in ["one compact post-report table", "one grouped question per module", "customer identities, orders, or transaction records", "F↔L handling: Preserve bidirectional links"]:
        if phrase not in body:
            issues.append(f"{label} missing module-level behavior: {phrase}")

    patterns = {str(item.get("id", "")): item for item in parse_yaml_items(root / "taxonomy" / "patterns.yml")}
    expected_names = {
        "fake-social-proof": "Unverified social proof",
        "fake-external-reviews": "Likely fabricated external reviews",
        "fake-social-media-reviews": "Confirmed or operator-confirmed fabricated platform reviews",
    }
    for pattern_id, expected_name in expected_names.items():
        item = patterns.get(pattern_id)
        if not item:
            issues.append(f"taxonomy/patterns.yml missing stable social-proof id: {pattern_id}")
            continue
        if item.get("name") != expected_name:
            issues.append(f"taxonomy/patterns.yml {pattern_id} must be named {expected_name}")
    for pattern_id in ["fake-external-reviews", "fake-social-media-reviews"]:
        if "us-ftc-reviews-rule" not in ensure_list(patterns.get(pattern_id, {}).get("maps_to_norms")):
            issues.append(f"taxonomy/patterns.yml {pattern_id} must candidate-map to us-ftc-reviews-rule")
    taxonomy_text = read_text(root / "taxonomy" / "patterns.yml")
    for phrase in ["ordinary footer social-media icons", "A missing visibly printed URL", "appearance alone", "operator-confirmed fake or fabricated social proof"]:
        if phrase.lower() not in taxonomy_text.lower():
            issues.append(f"taxonomy/patterns.yml missing social-proof safeguard: {phrase}")

    reference_root = resolve_skill_root(root) / "references"
    for name, phrases in REFERENCE_REQUIREMENTS.items():
        reference_path = reference_root / name
        if not reference_path.is_file():
            issues.append(f"missing skill reference: references/{name}")
            continue
        text = read_text(reference_path)
        for phrase in phrases:
            if phrase not in text:
                issues.append(f"references/{name} missing social-proof rule: {phrase}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    portable_core = is_portable_core(root)
    skill_root = resolve_skill_root(root)
    issues: list[str] = []
    warnings: list[str] = []

    fixture_root = root / "eval" / "policy_fixtures"
    fixtures = sorted(fixture_root.glob("*.md")) if fixture_root.exists() else []
    categories: set[str] = set()
    ids: set[str] = set()
    social_proof_fixture_seen = False
    for path in fixtures:
        fm, body = parse_frontmatter(path)
        label = relative(path, root)
        missing = sorted(REQUIRED_FIELDS - set(fm))
        if missing:
            issues.append(f"{label} missing fields: {', '.join(missing)}")
        fixture_id = str(fm.get("id", ""))
        if fixture_id in ids:
            issues.append(f"duplicate policy fixture id: {fixture_id}")
        ids.add(fixture_id)
        categories.add(str(fm.get("category", "")))
        if str(fm.get("category", "")) == "evidence_directive":
            expected_location = str(fm.get("expected_report_location", ""))
            if fixture_id == REQUESTED_INTEGRITY_FIXTURE_ID:
                if expected_location != "requested_assessment_summary_line":
                    issues.append(f"{label} must use requested_assessment_summary_line")
                for phrase in ["initial prompt explicitly requested", "exactly one", "--evidence-integrity-requested", "30 words"]:
                    if phrase not in body:
                        issues.append(f"{label} missing requested-disclosure behavior: {phrase}")
            else:
                if expected_location != "internal_evidence_integrity_state":
                    issues.append(f"{label} must keep default evidence-integrity handling internal")
                for phrase in ["internal evidence-integrity state", "Omit the public `Evidence integrity:` line"]:
                    if phrase not in body:
                        issues.append(f"{label} missing default internal-only behavior: {phrase}")
        if fixture_id == SOCIAL_PROOF_FIXTURE_ID:
            social_proof_fixture_seen = True
            validate_social_proof_fixture(path, fm, body, root, issues)
        if str(fm.get("category", "")) == "output_policy":
            missing_policy = sorted(OUTPUT_POLICY_FIELDS - set(fm))
            if missing_policy:
                issues.append(f"{label} missing output-policy fields: {', '.join(missing_policy)}")
            for field, expected in OUTPUT_POLICY_EXPECTED.items():
                if str(fm.get(field, "")).strip() != expected:
                    issues.append(f"{label} {field} must be {expected}")
        if "# Evidence" not in body or "# Expected Behavior" not in body:
            issues.append(f"{label} must contain Evidence and Expected Behavior sections")
        if len(body.split()) < 25:
            issues.append(f"{label} is too short to be a useful policy fixture")
    if len(fixtures) < 6:
        issues.append("eval/policy_fixtures must contain at least six controlled fixtures")
    missing_categories = REQUIRED_CATEGORIES - categories
    if missing_categories:
        issues.append(f"policy fixtures missing categories: {', '.join(sorted(missing_categories))}")
    if not social_proof_fixture_seen:
        issues.append(f"missing policy fixture: {SOCIAL_PROOF_FIXTURE_ID}")
    if REQUESTED_INTEGRITY_FIXTURE_ID not in ids:
        issues.append(f"missing policy fixture: {REQUESTED_INTEGRITY_FIXTURE_ID}")

    instruction_files = (
        [skill_root / "SKILL.md", root / "constitutions" / "GLOBAL.md"]
        if portable_core
        else [root / "AGENTS.md", root / "CLAUDE.md", root / "constitutions" / "GLOBAL.md"]
    )
    for path in instruction_files:
        if not path.is_file():
            issues.append(f"missing instruction file: {relative(path, root)}")
            continue
        text = read_text(path)
        if "evidence" not in text.lower():
            issues.append(f"{relative(path, root)} does not describe evidence handling")
        if path.name == "SKILL.md":
            for phrase in ["evaluation-workflow.md", "report-contract.md", "build_evaluation_context.py"]:
                if phrase not in text:
                    issues.append(f"{relative(path, root)} missing progressive-disclosure route: {phrase}")
        else:
            for phrase in ["Default output language is English", "initial operator prompt", "RESOURCE_LIMITS.json"]:
                if phrase not in text:
                    issues.append(f"{relative(path, root)} missing output-policy phrase: {phrase}")

    constitution = root / "constitutions" / "GLOBAL.md"
    if constitution.is_file():
        text = read_text(constitution)
        for phrase in ["Host system and developer instructions", "evidence only", "Statutory ceiling", "Observed enforcement benchmark", "Case-specific estimate", "Default output language is English", "initial operator prompt", "RESOURCE_LIMITS.json", "output-safety", "sub_jurisdiction", "material norm first"]:
            if phrase not in text:
                issues.append(f"constitutions/GLOBAL.md missing required policy phrase: {phrase}")

    routing_policy_paths = {
        "constitutions/GLOBAL.md": constitution,
        "references/evaluation-workflow.md": skill_root / "references" / "evaluation-workflow.md",
    }
    for label, rules in TRI_STATE_ROUTING_POLICY.items():
        path = routing_policy_paths[label]
        if not path.is_file():
            issues.append(f"missing tri-state routing policy file: {label}")
            continue
        text = read_text(path)
        if rules["required"] not in text:
            issues.append(f"{label} missing tri-state routing rule: {rules['required']}")
        if rules["obsolete"] in text:
            issues.append(f"{label} retains obsolete missing-fact abstention: {rules['obsolete']}")

    security_boundary = root / "SECURITY_BOUNDARY.md"
    if not security_boundary.is_file():
        issues.append("missing SECURITY_BOUNDARY.md")
    else:
        boundary_text = read_text(security_boundary)
        for phrase in ["host or webapp", "not an upload validator", "does not invoke a model", "context-window tokens", "--evidence-integrity-requested"]:
            if phrase not in boundary_text:
                issues.append(f"SECURITY_BOUNDARY.md missing boundary phrase: {phrase}")

    codex_skill = skill_root
    claude_skill = root / ".claude" / "skills" / "applaw"
    skill_frontmatter, skill_body = parse_frontmatter(codex_skill / "SKILL.md") if (codex_skill / "SKILL.md").is_file() else ({}, "")
    if set(skill_frontmatter) != {"name", "description"}:
        issues.append("skill SKILL.md frontmatter must contain only name and description")
    expected_skill_name = "applaw"
    if skill_frontmatter.get("name") != expected_skill_name:
        issues.append(f"skill name must be {expected_skill_name}")
    skill_description = str(skill_frontmatter.get("description", ""))
    if len(skill_description) < 80:
        issues.append("skill description is too short to cover its trigger surface")
    if len(skill_description) > 600:
        issues.append("skill description exceeds the cross-platform discovery budget")
    if re.search(r"\b(?:maintenance|packaging|portable releases?)\b", skill_description, re.IGNORECASE):
        issues.append("public skill description must not activate for KB maintenance or packaging")
    if not skill_body.strip():
        issues.append("skill SKILL.md has no instruction body")
    if portable_core:
        if (root / "skills").exists() or (root / ".claude").exists():
            issues.append("portable skill-root release must not contain nested Codex or Claude skill copies")
        if not (codex_skill / "agents" / "openai.yaml").is_file():
            issues.append("portable skill root must retain agents/openai.yaml")
        try:
            release_version = str(
                json.loads((root / "RELEASE_PROFILE.json").read_text(encoding="utf-8")).get("release_version", "")
            )
        except (OSError, json.JSONDecodeError):
            release_version = ""
        allowed_names = {expected_skill_name, f"{expected_skill_name}-v{release_version}"}
        if root.name not in allowed_names:
            issues.append("portable skill folder must use the skill name or its versioned release name")
    else:
        codex_files = skill_files(codex_skill)
        claude_files = skill_files(claude_skill)
        if set(codex_files) != set(claude_files):
            missing_claude = sorted(set(codex_files) - set(claude_files))
            extra_claude = sorted(set(claude_files) - set(codex_files))
            if missing_claude:
                issues.append(f"Claude skill missing files: {', '.join(missing_claude)}")
            if extra_claude:
                issues.append(f"Claude skill has extra files: {', '.join(extra_claude)}")
        for rel_path in sorted(set(codex_files) & set(claude_files)):
            if digest(codex_files[rel_path]) != digest(claude_files[rel_path]):
                issues.append(f"Codex/Claude skill mismatch: {rel_path}")

    contract = codex_skill / "references" / "report-contract.md"
    if contract.is_file():
        text = read_text(contract)
        for phrase in ["Public Report Contract v3", "RISK: <very low|low|medium|high|very high>", "Never expose the number", "Liability and Consequences", "Evidence integrity", "--evidence-integrity-requested", "Estimate status: Not estimable from the supplied interface and business data.", "Output Language And Style", "Default output language is English", "initial operator prompt", "sub_jurisdiction", "material norm first"]:
            if phrase not in text:
                issues.append(f"report contract missing v3 phrase: {phrase}")

    style_reference = codex_skill / "references" / "output-style.md"
    if not style_reference.is_file():
        issues.append("missing skill reference: references/output-style.md")
    else:
        style_text = read_text(style_reference)
        for phrase in ["Default output language is English.", "initial operator prompt", "plain, conversational"]:
            if phrase not in style_text:
                issues.append(f"references/output-style.md missing required phrase: {phrase}")

    output_safety_reference = codex_skill / "references" / "output-safety.md"
    if not output_safety_reference.is_file():
        issues.append("missing skill reference: references/output-safety.md")
    else:
        output_safety_text = read_text(output_safety_reference)
        for phrase in ["validate_output_safety.py", "prompt or constitution excerpts", "not a complete data-loss-prevention system"]:
            if phrase not in output_safety_text:
                issues.append(f"references/output-safety.md missing required phrase: {phrase}")

    skill_text = read_text(codex_skill / "SKILL.md") if (codex_skill / "SKILL.md").is_file() else ""
    for phrase in [
        "Report Runtime Gate",
        "validate_live_report.py",
        "report-contract.md",
        "output-safety.md",
        "private numeric score",
        "return the passing text unchanged",
    ]:
        if phrase not in skill_text:
            issues.append(f"SKILL.md missing live report-gate phrase: {phrase}")
    metadata = codex_skill / "agents" / "openai.yaml"
    if metadata.is_file():
        metadata_text = read_text(metadata)
        for phrase in ["Report Contract v3", "allow_implicit_invocation: true"]:
            if phrase not in metadata_text:
                issues.append(f"agents/openai.yaml missing discovery metadata: {phrase}")

    for reference_name in ("report-contract.md", "evaluation-workflow.md", "kb-schema.md"):
        reference_path = codex_skill / "references" / reference_name
        if reference_path.is_file():
            reference_text = read_text(reference_path)
            if len(reference_text.splitlines()) > 100 and "## Contents" not in reference_text:
                issues.append(f"references/{reference_name} exceeds 100 lines without a Contents section")

    layout = "flattened skill root" if portable_core else "Codex and Claude skill copies compared"
    warnings.append(f"policy summary: {len(fixtures)} fixtures across {len(categories)} categories; {layout}")
    return print_result("Policy and instruction validation", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())
