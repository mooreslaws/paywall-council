#!/usr/bin/env python3
"""Validate checkout-funnel public Report Contract v3 structure and liability hygiene."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from _kb import parse_yaml_items, print_result, relative, resolve_kb_root


EXPECTED_SECTIONS = [
    "Assessment Summary",
    "Material Findings",
    "Liability and Consequences",
    "Mitigating and Low-Risk Elements",
    "Observed Without a Mapped Norm",
    "Missing Context",
    "Priority Actions",
    "Disclaimer",
]

FINDING_FIELDS = [
    "Severity",
    "Observed evidence",
    "Pattern",
    "Risk explanation",
    "Applicable norm",
    "Comparable KB authority",
    "Linked liability blocks",
    "Confidence and limitations",
    "Recommended correction",
]

LIABILITY_FIELDS = [
    "Linked findings",
    "Liability trigger",
    "Consumer or contract remedies",
    "Public enforcement",
    "Private exposure",
    "Monetary exposure",
    "Observed enforcement benchmark",
    "Non-monetary orders",
    "Authority citations",
    "Estimate status and limitations",
]

FIELD_WORD_LIMITS = {
    "Severity": 1,
    "Observed evidence": 80,
    "Pattern": 25,
    "Risk explanation": 80,
    "Applicable norm": 70,
    "Comparable KB authority": 55,
    "Linked liability blocks": 8,
    "Confidence and limitations": 60,
    "Recommended correction": 60,
}

LIABILITY_WORD_LIMITS = {
    "Linked findings": 8,
    "Liability trigger": 85,
    "Consumer or contract remedies": 70,
    "Public enforcement": 70,
    "Private exposure": 70,
    "Monetary exposure": 90,
    "Observed enforcement benchmark": 95,
    "Non-monetary orders": 70,
    "Authority citations": 55,
    "Estimate status and limitations": 75,
}

DISCLAIMER = (
    "This report is a risk assessment based on the supplied interface and available context. "
    "It is not legal advice."
)
REVIEW_MODULE_QUESTION = (
    "Are the displayed social-platform reviews or testimonials fake, fabricated, purchased, or presented without a genuine "
    "underlying customer experience? Reply Yes, No, or Unknown. If No, you may optionally provide the original post, "
    "review-page, platform ID, or official-widget confirmation."
)
REVIEW_MODULE_QUESTION_LINE = f"“{REVIEW_MODULE_QUESTION}”"
NOT_ESTIMABLE = "Estimate status: Not estimable from the supplied interface and business data."
NEUTRAL_JURISDICTIONS = "Jurisdictions assessed: Not established; no jurisdiction-specific legal conclusion was made."
UNSUPPORTED_JURISDICTION_DISCLOSURE = (
    "- An unspecified unsupported market was excluded from legal analysis."
)
JURISDICTIONAL_LEGAL_MARKERS = re.compile(
    r"\b(?:United States|United Kingdom|European Union|ROSCA|FTC Act|DMCC Act|"
    r"Consumer Rights Directive|Unfair Commercial Practices Directive)\b",
    re.IGNORECASE,
)
AUTHORITY_MARKERS = {
    "US": re.compile(
        r"\b(?:Federal Trade Commission|FTC|ROSCA|Restore Online Shoppers' Confidence Act|FTC Act|15 U\.S\.C\.)\b",
        re.IGNORECASE,
    ),
    "UK": re.compile(
        r"\b(?:Competition and Markets Authority|CMA|DMCC|Digital Markets, Competition and Consumers Act|SI 2013/3134)\b",
        re.IGNORECASE,
    ),
    "EU": re.compile(
        r"\b(?:European Commission|CPC Network|Court of Justice of the European Union|CJEU|"
        r"Unfair Commercial Practices Directive|Consumer Rights Directive|Directive 2005/29/EC|Directive 2011/83/EU)\b",
        re.IGNORECASE,
    ),
}
COUNTRY_AUTHORITY_MARKERS = {
    "FR": re.compile(r"\b(?:France|French|CNIL|Data Protection Act Article 82)\b", re.IGNORECASE),
    "NL": re.compile(r"\b(?:Netherlands|Dutch|ACM|Rotterdam District Court)\b", re.IGNORECASE),
}

BANNED_PATTERNS = [
    ("raw URL", re.compile(r"https?://", re.IGNORECASE)),
    ("file URI", re.compile(r"file://", re.IGNORECASE)),
    ("absolute Windows path", re.compile(r"\b[A-Za-z]:[\\/]")),
    ("Markdown link", re.compile(r"\[[^\]]+\]\([^)]+\)")),
    ("internal repository path", re.compile(r"\b(?:taxonomy|cases|assets|case_law|downloaded_pdfs|generated|outputs|new|tmp)[\\/]", re.IGNORECASE)),
    ("repository line citation", re.compile(r"\b[\w.-]+\.(?:yml|yaml|md|json|py):\d+\b", re.IGNORECASE)),
    ("internal norm or outcome id", re.compile(r"\b(?:us|eu|uk)-[a-z0-9]+(?:-[a-z0-9]+)+\b")),
    ("KB metadata", re.compile(r"\b(?:KB used|KB root|source screenshot)\b", re.IGNORECASE)),
    ("internal pipeline label", re.compile(r"\bA[1-8]\b")),
    ("internal process commentary", re.compile(r"\b(?:vision decomposition|legal dossier|pattern specialists|verifier)\b", re.IGNORECASE)),
    ("tool or model commentary", re.compile(r"\b(?:I reviewed|I used|the skill|the model|the agent)\b", re.IGNORECASE)),
    ("inline code marker", re.compile(r"`")),
    ("code fence", re.compile(r"```")),
    ("public numeric score", re.compile(r"\b(?:risk\s+)?score\s*(?:is|of|:)?\s*[1-9]\d?(?:/100)?\b", re.IGNORECASE)),
    ("legacy risk band", re.compile(r"\bRisk band:\s*", re.IGNORECASE)),
    ("predictive ceiling language", re.compile(r"\b(?:likely|expected|typical|probable) (?:fine|penalty|maximum|ceiling)\b", re.IGNORECASE)),
]


def word_count(value: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", value, re.UNICODE))


def nonempty(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


def split_post_report(lines: list[str]) -> tuple[list[str], list[str]]:
    disclaimer_indexes = [index for index, line in enumerate(lines) if line.strip() == DISCLAIMER]
    if not disclaimer_indexes:
        return lines, []
    index = disclaimer_indexes[-1]
    return lines[: index + 1], nonempty(lines[index + 1 :])


def validate_post_report_suffix(
    label: str,
    suffix: list[str],
    report_text: str,
    issues: list[str],
) -> None:
    if not suffix:
        return
    review_context = (
        "Review authenticity:" in report_text
        and any(
            marker in report_text
            for marker in (
                "Unverified social proof",
                "Likely fabricated external reviews",
                "Confirmed or operator-confirmed fabricated platform reviews",
            )
        )
    )
    if not review_context:
        issues.append(f"{label} has a post-report review question without corresponding unresolved review context")
    if suffix == [REVIEW_MODULE_QUESTION_LINE]:
        return
    if len(suffix) < 3 or suffix[:2] != ["| Module | Question |", "| --- | --- |"]:
        issues.append(f"{label} contains unauthorized content after the disclaimer")
        return
    rows = suffix[2:]
    if not 1 <= len(rows) <= 8:
        issues.append(f"{label} post-report review table must contain 1-8 rows")
    for position, row in enumerate(rows, start=1):
        match = re.fullmatch(r"\| ([^|]+) \| ([^|]+) \|", row)
        if not match:
            issues.append(f"{label} post-report review table row {position} is malformed")
            continue
        module, question = match.groups()
        if not module.strip() or word_count(module) > 20:
            issues.append(f"{label} post-report review table row {position} has an invalid module label")
        if question.strip() != REVIEW_MODULE_QUESTION:
            issues.append(f"{label} post-report review table row {position} must use the exact authorized question")


def section_map(lines: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    headings = [(i, line[3:].strip()) for i, line in enumerate(lines) if line.startswith("## ")]
    sections: dict[str, list[str]] = {}
    for position, (index, name) in enumerate(headings):
        end = headings[position + 1][0] if position + 1 < len(headings) else len(lines)
        sections[name] = lines[index + 1 : end]
    return [name for _, name in headings], sections


def parse_id_list(value: str, prefix: str) -> set[str]:
    return set(re.findall(rf"\b{prefix}\d+\b", value))


def stated_jurisdictions(line: str) -> set[str]:
    allowed: set[str] = set()
    if re.search(r"\b(?:United States|US)\b", line, re.IGNORECASE):
        allowed.add("US")
    if re.search(r"\b(?:United Kingdom|UK)\b", line, re.IGNORECASE):
        allowed.add("UK")
    if re.search(r"\b(?:European Union|EU|France)\b", line, re.IGNORECASE):
        allowed.add("EU")
    return allowed


def stated_sub_jurisdictions(line: str) -> set[str]:
    allowed: set[str] = set()
    if re.search(r"\b(?:France|French)\b", line, re.IGNORECASE):
        allowed.add("FR")
    if re.search(r"\b(?:Netherlands|Dutch)\b", line, re.IGNORECASE):
        allowed.add("NL")
    return allowed


def procedural_primary_markers(root: Path) -> list[str]:
    markers: list[str] = []
    for norm in parse_yaml_items(root / "taxonomy" / "norms.yml"):
        if norm.get("type") != "procedural":
            continue
        for field in ("instrument", "citation"):
            value = str(norm.get(field, "")).strip().casefold()
            if value:
                markers.append(value)
    return markers


def normalize_authority(value: object) -> str:
    text = str(value or "").casefold().replace("§§", " sections ").replace("§", " section ")
    text = re.sub(r"\bsections\b", "section", text)
    text = re.sub(r"\barticles\b|\barts\b", "article", text)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def authority_parts(norm: dict) -> tuple[str, str, str, str]:
    instrument = normalize_authority(norm.get("instrument"))
    citation = normalize_authority(norm.get("citation"))
    match = re.match(r"^(.+?)\b(section|article|part|schedule)\s+(.+)$", instrument)
    if not match:
        return instrument, citation, "", ""
    family = match.group(1).strip()
    provision = f"{match.group(2)} {match.group(3)}".strip()
    return instrument, citation, family, provision


def matched_material_norm_ids(value: str, root: Path) -> set[str]:
    """Map human-readable instruments/citations to registry ids deterministically."""
    normalized = normalize_authority(value)
    material = [
        norm
        for norm in parse_yaml_items(root / "taxonomy" / "norms.yml")
        if norm.get("type") == "material"
    ]
    parts = {str(norm.get("id")): authority_parts(norm) for norm in material}
    provision_counts: dict[str, int] = {}
    for _instrument, _citation, _family, provision in parts.values():
        if provision:
            provision_counts[provision] = provision_counts.get(provision, 0) + 1

    matched: set[str] = set()
    for norm in material:
        norm_id = str(norm.get("id"))
        instrument, citation, family, provision = parts[norm_id]
        direct = any(
            marker and marker in normalized
            for marker in (instrument, citation)
        )
        # The provision has to appear whole, not just its digits. Comparing
        # digits alone made "section 5 n" match a correct "FTC Act Section
        # 5(a), 15 U.S.C. 45(a)" citation, because both provisions carry the
        # number 5 and only the letter tells them apart. Every report citing
        # FTC Section 5(a) therefore matched Section 5(n) as well, and 5(n) is
        # rarely in the routed slice, so the report was rejected for naming an
        # authority it never named. Three live runs died on this.
        family_and_provision = bool(
            family and family in normalized and provision and provision in normalized
        )
        unique_provision = bool(
            provision
            and provision_counts.get(provision) == 1
            and provision in normalized
        )
        if direct or family_and_provision or unique_provision:
            matched.add(norm_id)
    return matched


def validate_bullets(label: str, section: str, lines: list[str], issues: list[str], *, minimum: int, maximum: int, word_limit: int, allow_none: bool) -> None:
    content = nonempty(lines)
    if allow_none and content == ["None."]:
        return
    if not minimum <= len(content) <= maximum:
        issues.append(f"{label} {section} must contain {minimum}-{maximum} bullets")
    for line in content:
        if not line.startswith("- "):
            issues.append(f"{label} {section} contains non-bullet content: {line}")
        elif word_count(line[2:]) > word_limit:
            issues.append(f"{label} {section} bullet exceeds {word_limit} words")


def parse_blocks(label: str, lines: list[str], issues: list[str], *, prefix: str, fields: list[str], limits: dict[str, int]) -> tuple[dict[str, dict[str, str]], bool]:
    content = nonempty(lines)
    if content == ["None."]:
        return {}, True
    headings = [(i, line.strip()) for i, line in enumerate(lines) if line.startswith("### ")]
    if not headings:
        issues.append(f"{label} section must contain numbered {prefix} headings or None.")
        return {}, False
    if nonempty(lines[: headings[0][0]]):
        issues.append(f"{label} section has content before {prefix}1")
    blocks: dict[str, dict[str, str]] = {}
    for position, (index, heading) in enumerate(headings, start=1):
        match = re.fullmatch(rf"### ({prefix})(\d+) - (\S.+)", heading)
        block_id = f"{prefix}{position}"
        if not match:
            issues.append(f"{label} invalid {prefix} heading: {heading}")
        else:
            block_id = f"{match.group(1)}{match.group(2)}"
            if int(match.group(2)) != position:
                issues.append(f"{label} {prefix} blocks must be numbered consecutively")
        end = headings[position][0] if position < len(headings) else len(lines)
        body = nonempty(lines[index + 1 : end])
        if len(body) != len(fields):
            issues.append(f"{label} {block_id} must contain exactly {len(fields)} one-line fields; found {len(body)}")
        values: dict[str, str] = {}
        for field_index, field in enumerate(fields):
            if field_index >= len(body):
                continue
            expected = f"{field}: "
            line = body[field_index]
            if not line.startswith(expected):
                issues.append(f"{label} {block_id} expected {field} at position {field_index + 1}")
                continue
            value = line[len(expected) :].strip()
            values[field] = value
            if not value:
                issues.append(f"{label} {block_id} has empty {field}")
            if word_count(value) > limits[field]:
                issues.append(f"{label} {block_id} {field} exceeds {limits[field]} words")
        blocks[block_id] = values
    return blocks, False


def validate_report(
    path: Path,
    root: Path,
    *,
    evidence_integrity_requested: bool = False,
    text_override: str | None = None,
    label_override: str | None = None,
    allowed_material_norm_ids: set[str] | None = None,
    conditional_material_norm_ids: set[str] | None = None,
    require_unsupported_jurisdiction_disclosure: bool = False,
) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    warnings: list[str] = []
    label = label_override or relative(path, root)
    if text_override is None:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except Exception as exc:
            return [f"{label} cannot be read: {exc}"], warnings
    else:
        text = text_override
    response_lines = text.splitlines()
    lines, post_report_suffix = split_post_report(response_lines)
    report_text = "\n".join(lines)

    integrity_lines = [
        line.strip()
        for line in response_lines
        if re.match(r"^\s*Evidence\s+integrity\s*:", line, re.IGNORECASE)
    ]
    if evidence_integrity_requested:
        if len(integrity_lines) != 1:
            issues.append(f"{label} must contain exactly one Evidence integrity line because disclosure was requested")
    elif integrity_lines:
        issues.append(f"{label} contains an Evidence integrity line without an explicit initial-prompt request")

    if word_count(text) > 3200:
        issues.append(f"{label} exceeds 3200 words")
    if any(line != line.rstrip() for line in response_lines):
        issues.append(f"{label} contains trailing whitespace")
    if "\n\n\n" in text:
        issues.append(f"{label} contains more than one consecutive blank line")
    if any(line.lstrip().startswith(">") for line in response_lines):
        issues.append(f"{label} contains a blockquote")
    if any(line.lstrip().startswith("|") for line in lines):
        issues.append(f"{label} contains a table")
    for description, pattern in BANNED_PATTERNS:
        if pattern.search(text):
            issues.append(f"{label} contains prohibited {description}")

    h1 = [line for line in lines if line.startswith("# ")]
    if len(h1) != 1 or not h1[0].startswith("# Checkout-Funnel Risk Assessment: "):
        issues.append(f"{label} must contain exactly one standard report title")
    first_content = next((line for line in lines if line.strip()), "")
    if not first_content.startswith("# Checkout-Funnel Risk Assessment: "):
        issues.append(f"{label} must begin with the standard report title and no introductory prose")
    headings, sections = section_map(lines)
    if headings != EXPECTED_SECTIONS:
        issues.append(f"{label} level-two section order must be exactly: {', '.join(EXPECTED_SECTIONS)}")
    if not h1 or not headings:
        return issues, warnings

    title_index = lines.index(h1[0])
    first_h2 = next(i for i, line in enumerate(lines) if line.startswith("## "))
    preamble = nonempty(lines[title_index + 1 : first_h2])
    jurisdiction_line = ""
    if len(preamble) != 2:
        issues.append(f"{label} preamble must contain exactly assessment date and jurisdictions assessed")
    else:
        if not re.fullmatch(r"Assessment date: \d{4}-\d{2}-\d{2}", preamble[0]):
            issues.append(f"{label} has invalid Assessment date line")
        if not re.fullmatch(r"Jurisdictions assessed: \S.+", preamble[1]):
            issues.append(f"{label} has invalid Jurisdictions assessed line")
        jurisdiction_line = preamble[1]
        if re.search(r"\b(?:OTHER|worldwide)\b", jurisdiction_line, re.IGNORECASE):
            issues.append(
                f"{label} Jurisdictions assessed must list only supported US, EU, or UK scope"
            )
        if preamble[1] == NEUTRAL_JURISDICTIONS and JURISDICTIONAL_LEGAL_MARKERS.search(text):
            issues.append(f"{label} uses jurisdiction-specific legal language despite an unestablished target jurisdiction")
    if any(name not in sections for name in EXPECTED_SECTIONS):
        return issues, warnings

    summary = nonempty(sections["Assessment Summary"])
    risk_label = ""
    expected_summary_lines = 3 if evidence_integrity_requested else 2
    if len(summary) != expected_summary_lines:
        requirement = (
            "RISK, Verdict, and exactly one requested Evidence integrity line"
            if evidence_integrity_requested
            else "RISK and Verdict only"
        )
        issues.append(f"{label} Assessment Summary must contain {requirement}")
    else:
        risk_match = re.fullmatch(r"RISK: (very low|low|medium|high|very high)", summary[0])
        verdict_match = re.fullmatch(r"Verdict: (\S.+)", summary[1])
        if not risk_match:
            issues.append(f"{label} has invalid RISK line")
        else:
            risk_label = risk_match.group(1)
        if not verdict_match or word_count(verdict_match.group(1) if verdict_match else "") > 80:
            issues.append(f"{label} Verdict is missing or exceeds 80 words")
        if evidence_integrity_requested:
            integrity_match = re.fullmatch(r"Evidence integrity: (\S.+)", summary[2])
            if not integrity_match or word_count(integrity_match.group(1)) > 30:
                issues.append(f"{label} Evidence integrity is invalid or exceeds 30 words")

    findings, findings_none = parse_blocks(label, sections["Material Findings"], issues, prefix="F", fields=FINDING_FIELDS, limits=FIELD_WORD_LIMITS)
    liability, liability_none = parse_blocks(label, sections["Liability and Consequences"], issues, prefix="L", fields=LIABILITY_FIELDS, limits=LIABILITY_WORD_LIMITS)

    if risk_label in {"medium", "high", "very high"} and not findings:
        issues.append(f"{label} medium-or-higher risk requires a material finding")
    if risk_label in {"very low", "low"} and findings:
        issues.append(f"{label} very-low or low risk cannot contain material findings")
    if bool(findings) != bool(liability):
        issues.append(f"{label} material findings and liability blocks must either both exist or both be None")
    if findings_none != liability_none:
        issues.append(f"{label} finding/liability None states do not match")

    for finding_id, values in findings.items():
        if values.get("Severity") not in {"Medium", "High"}:
            issues.append(f"{label} {finding_id} Severity must be Medium or High")
        confidence = values.get("Confidence and limitations", "")
        if confidence and not re.match(r"^(?:High|Medium) - \S", confidence):
            issues.append(f"{label} {finding_id} Confidence and limitations must start with High - or Medium -")
        authority = values.get("Comparable KB authority", "").lower()
        if authority and not any(marker in authority for marker in ["complaint", "notice", "order", "settlement", "judgment", "decision", "case"]):
            issues.append(f"{label} {finding_id} Comparable KB authority must state posture")
        links = parse_id_list(values.get("Linked liability blocks", ""), "L")
        if not links:
            issues.append(f"{label} {finding_id} must link at least one liability block")
        for linked in links:
            if linked not in liability:
                issues.append(f"{label} {finding_id} links missing liability block {linked}")
        applicable = values.get("Applicable norm", "").casefold()
        for marker in procedural_primary_markers(root):
            if marker in applicable:
                issues.append(
                    f"{label} {finding_id} uses a procedural norm in the primary Applicable norm field"
                )
                break
        if allowed_material_norm_ids is not None and applicable:
            conditional_ids = conditional_material_norm_ids or set()
            matched_norms = matched_material_norm_ids(applicable, root)
            if not matched_norms:
                issues.append(
                    f"{label} {finding_id} Applicable norm does not map to a material authority in the selected KB"
                )
            elif not matched_norms.issubset(allowed_material_norm_ids | conditional_ids):
                issues.append(
                    f"{label} {finding_id} Applicable norm names an authority outside the routed legal slice"
                )
            elif not matched_norms.issubset(allowed_material_norm_ids):
                # Conditional citation: the routed facts for this authority are
                # not established, so the finding must carry the condition on
                # its face - Medium confidence (never High) and an explicit
                # "conditional on ..." clause naming what remains unestablished.
                # This keeps the anti-over-citation discipline while letting
                # the report still name the norm and its liability exposure.
                if not confidence.startswith("Medium - "):
                    issues.append(
                        f"{label} {finding_id} conditional authority requires Medium confidence"
                    )
                if "conditional on" not in confidence.casefold():
                    issues.append(
                        f"{label} {finding_id} conditional authority requires an explicit 'conditional on ...' clause in Confidence and limitations"
                    )

    for liability_id, values in liability.items():
        links = parse_id_list(values.get("Linked findings", ""), "F")
        if not links:
            issues.append(f"{label} {liability_id} must link at least one finding")
        for linked in links:
            if linked not in findings:
                issues.append(f"{label} {liability_id} links missing finding {linked}")
            elif liability_id not in parse_id_list(findings[linked].get("Linked liability blocks", ""), "L"):
                issues.append(f"{label} {linked} and {liability_id} are not linked in both directions")
        monetary = values.get("Monetary exposure", "").lower()
        if "not an expected outcome" not in monetary:
            issues.append(f"{label} {liability_id} Monetary exposure must label the ceiling as not an expected outcome")
        benchmark = values.get("Observed enforcement benchmark", "")
        if benchmark != "None identified.":
            lower = benchmark.lower()
            if not any(marker in lower for marker in ["final notice", "order", "settlement", "judgment", "final decision", "consent order"]):
                issues.append(f"{label} {liability_id} benchmark must state final posture")
            if not any(marker in lower for marker in ["non-predictive", "not predictive", "limited comparator", "not comparable", "comparison is limited"]):
                issues.append(f"{label} {liability_id} benchmark must state a non-predictive comparability limit")
        estimate = values.get("Estimate status and limitations", "")
        if NOT_ESTIMABLE not in estimate and not estimate.startswith("Supported estimate -"):
            issues.append(f"{label} {liability_id} must use the exact not-estimable sentence or a supported-estimate declaration")

    allowed_jurisdictions = stated_jurisdictions(jurisdiction_line)
    allowed_sub_jurisdictions = stated_sub_jurisdictions(jurisdiction_line)
    authority_text = " ".join(
        [
            value
            for values in findings.values()
            for field, value in values.items()
            if field in {"Applicable norm", "Comparable KB authority"}
        ]
        + [
            value
            for values in liability.values()
            for field, value in values.items()
            if field
            in {
                "Liability trigger",
                "Public enforcement",
                "Observed enforcement benchmark",
                "Authority citations",
            }
        ]
    )
    for jurisdiction, marker in AUTHORITY_MARKERS.items():
        if jurisdiction not in allowed_jurisdictions and marker.search(authority_text):
            issues.append(
                f"{label} cites a {jurisdiction} authority outside the jurisdictions stated in the report preamble"
            )
    for sub_jurisdiction, marker in COUNTRY_AUTHORITY_MARKERS.items():
        if sub_jurisdiction not in allowed_sub_jurisdictions and marker.search(authority_text):
            issues.append(
                f"{label} cites a {sub_jurisdiction} country-specific authority without that country in the report preamble"
            )

    for section_name in EXPECTED_SECTIONS:
        if section_name not in {"Material Findings", "Liability and Consequences"} and any(line.startswith("### ") for line in sections[section_name]):
            issues.append(f"{label} {section_name} must not contain level-three headings")

    validate_bullets(label, "Mitigating and Low-Risk Elements", sections["Mitigating and Low-Risk Elements"], issues, minimum=1, maximum=8, word_limit=35, allow_none=True)
    # The outlet that keeps a report whole. A pattern the Examiner saw but no
    # routed authority reaches used to leave Counsel with two bad options: stay
    # silent, or reach for the obvious instrument and lose the entire report to
    # the citation gate. Neither is what a reader needs. Naming the pattern
    # without a legal conclusion is.
    validate_bullets(
        label,
        "Observed Without a Mapped Norm",
        sections["Observed Without a Mapped Norm"],
        issues,
        minimum=1,
        maximum=10,
        word_limit=45,
        allow_none=True,
    )
    for line in nonempty(sections["Observed Without a Mapped Norm"]):
        if matched_material_norm_ids(line, root):
            issues.append(
                f"{label} Observed Without a Mapped Norm must not cite an authority: "
                "an observation with a citation belongs in Material Findings"
            )
            break

    validate_bullets(label, "Missing Context", sections["Missing Context"], issues, minimum=1, maximum=6, word_limit=35, allow_none=True)
    if require_unsupported_jurisdiction_disclosure and UNSUPPORTED_JURISDICTION_DISCLOSURE not in nonempty(
        sections["Missing Context"]
    ):
        issues.append(
            f"{label} Missing Context must contain the required unsupported-jurisdiction exclusion disclosure"
        )
    validate_bullets(label, "Priority Actions", sections["Priority Actions"], issues, minimum=3, maximum=5, word_limit=40, allow_none=False)
    if nonempty(sections["Disclaimer"]) != [DISCLAIMER]:
        issues.append(f"{label} Disclaimer must match the standard sentence exactly")
    validate_post_report_suffix(label, post_report_suffix, report_text, issues)
    return issues, warnings


def validate_integrity_regressions(root: Path) -> list[str]:
    fixture_path = root / "eval" / "report_validation_cases.json"
    if not fixture_path.is_file():
        return ["missing report validator fixture: eval/report_validation_cases.json"]
    try:
        fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot load report validator fixtures: {exc}"]
    issues: list[str] = []
    seen: set[str] = set()
    for case in fixtures:
        case_id = str(case.get("id", ""))
        if not case_id or case_id in seen:
            issues.append(f"invalid or duplicate report validator fixture id: {case_id!r}")
            continue
        seen.add(case_id)
        base = root / str(case.get("base_sample", ""))
        if not base.is_file():
            issues.append(f"{case_id}: base sample does not exist: {case.get('base_sample')}")
            continue
        text = str(case.get("text_override", "")) or base.read_text(encoding="utf-8-sig")
        additions = [str(value) for value in case.get("summary_append_lines", [])]
        if additions:
            lines = text.splitlines()
            verdict_index = next(
                (index for index, line in enumerate(lines) if line.startswith("Verdict: ")),
                None,
            )
            if verdict_index is None:
                issues.append(f"{case_id}: base sample has no Verdict line")
                continue
            lines[verdict_index + 1 : verdict_index + 1] = additions
            text = "\n".join(lines) + ("\n" if text.endswith(("\n", "\r")) else "")
        replacements = case.get("replace_prefix_lines", {})
        if replacements:
            lines = text.splitlines()
            for prefix, replacement in replacements.items():
                indexes = [index for index, line in enumerate(lines) if line.startswith(str(prefix))]
                if len(indexes) != 1:
                    issues.append(f"{case_id}: expected exactly one line beginning {prefix!r}")
                    continue
                lines[indexes[0]] = str(replacement)
            text = "\n".join(lines) + ("\n" if text.endswith(("\n", "\r")) else "")
        remove_prefixes = [str(value) for value in case.get("remove_prefix_lines", [])]
        if remove_prefixes:
            lines = text.splitlines()
            for prefix in remove_prefixes:
                indexes = [index for index, line in enumerate(lines) if line.startswith(prefix)]
                if len(indexes) != 1:
                    issues.append(f"{case_id}: expected exactly one line beginning {prefix!r}")
                    continue
                del lines[indexes[0]]
            text = "\n".join(lines) + ("\n" if text.endswith(("\n", "\r")) else "")
        exact_replacements = case.get("replace_exact", {})
        for original, replacement in exact_replacements.items():
            if text.count(str(original)) != 1:
                issues.append(f"{case_id}: expected exactly one occurrence of replacement target")
                continue
            text = text.replace(str(original), str(replacement), 1)
        replace_sections = case.get("replace_sections", {})
        remove_sections = [str(value) for value in case.get("remove_sections", [])]
        if replace_sections or remove_sections:
            lines = text.splitlines()
            for section_name in [*replace_sections, *remove_sections]:
                heading = f"## {section_name}"
                indexes = [index for index, line in enumerate(lines) if line == heading]
                if len(indexes) != 1:
                    issues.append(f"{case_id}: expected exactly one section {section_name!r}")
                    continue
                start = indexes[0]
                end = next(
                    (index for index in range(start + 1, len(lines)) if lines[index].startswith("## ")),
                    len(lines),
                )
                if section_name in remove_sections:
                    del lines[start:end]
                else:
                    replacement_lines = str(replace_sections[section_name]).splitlines()
                    lines[start + 1 : end] = ["", *replacement_lines, ""]
            text = "\n".join(lines) + "\n"
        prepend = [str(value) for value in case.get("prepend_lines", [])]
        if prepend:
            text = "\n".join([*prepend, text])
        allowed_material_norm_ids = (
            {str(value) for value in case.get("allowed_material_norm_ids", [])}
            if "allowed_material_norm_ids" in case
            else None
        )
        conditional_material_norm_ids = {
            str(value) for value in case.get("conditional_material_norm_ids", [])
        }
        require_unsupported_jurisdiction_disclosure = bool(
            case.get("require_unsupported_jurisdiction_disclosure", False)
        )
        case_issues, _ = validate_report(
            base,
            root,
            evidence_integrity_requested=bool(case.get("evidence_integrity_requested", False)),
            text_override=text,
            label_override=f"report-validator-fixture:{case_id}",
            allowed_material_norm_ids=allowed_material_norm_ids,
            conditional_material_norm_ids=conditional_material_norm_ids,
            require_unsupported_jurisdiction_disclosure=require_unsupported_jurisdiction_disclosure,
        )
        expected = str(case.get("expected_status", ""))
        actual = "reject" if case_issues else "pass"
        if actual != expected:
            issues.append(f"{case_id}: expected {expected}, got {actual}")
        expected_fragment = str(case.get("expected_issue_contains", ""))
        if expected_fragment and not any(expected_fragment in issue for issue in case_issues):
            issues.append(f"{case_id}: no validation issue contained {expected_fragment!r}")
    required = {
        "default-omitted-pass",
        "default-line-reject",
        "requested-valid-pass",
        "requested-missing-reject",
        "requested-duplicate-reject",
        "requested-over-30-words-reject",
        "procedural-primary-norm-reject",
        "country-specific-authority-without-country-reject",
        "informal-narrative-reject",
        "mandatory-section-missing-reject",
        "material-risk-without-f-block-reject",
        "finding-without-linked-liability-reject",
        "liability-without-backlink-reject",
        "missing-finding-field-reject",
        "missing-liability-field-reject",
        "incorrect-finding-numbering-reject",
        "incorrect-liability-numbering-reject",
        "low-risk-complete-none-pass",
        "no-jurisdiction-complete-none-pass",
        "incorrect-disclaimer-reject",
        "introductory-prose-reject",
        "very-low-label-pass",
        "very-high-label-pass",
        "invalid-risk-label-reject",
        "public-numeric-score-reject",
        "routed-authority-pass",
        "outside-routed-slice-reject",
        "negative-option-reviews-rule-reject",
        "multiple-routed-authorities-pass",
        "unsupported-jurisdiction-disclosure-required-reject",
        "unsupported-jurisdiction-disclosure-pass",
        "unsupported-jurisdiction-preamble-reject",
        "conditional-authority-pass",
        "conditional-authority-high-confidence-reject",
        "conditional-authority-missing-clause-reject",
    }
    missing = required - seen
    if missing:
        issues.append(f"report validator fixtures missing cases: {', '.join(sorted(missing))}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", help="Report files; defaults to eval/report_samples/*.md")
    parser.add_argument("--kb", default=None, help="KB root")
    parser.add_argument("--samples-dir", default=None, help="Alternate report sample directory")
    parser.add_argument(
        "--evidence-integrity-requested",
        action="store_true",
        help="Require exactly one valid Evidence integrity line because the initial operator prompt requested disclosure",
    )
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    if args.paths:
        paths = [Path(raw).resolve() for raw in args.paths]
    else:
        samples = Path(args.samples_dir).resolve() if args.samples_dir else root / "eval" / "report_samples"
        paths = sorted(samples.glob("*.md")) if samples.exists() else []
    issues: list[str] = []
    warnings: list[str] = []
    if not paths:
        issues.append("no report files found")
    for path in paths:
        if not path.is_file():
            issues.append(f"report path is not a file: {path}")
            continue
        path_issues, path_warnings = validate_report(
            path,
            root,
            evidence_integrity_requested=args.evidence_integrity_requested,
        )
        issues.extend(path_issues)
        warnings.extend(path_warnings)
    issues.extend(validate_integrity_regressions(root))
    return print_result(f"Report validation ({len(paths)} file(s))", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())
