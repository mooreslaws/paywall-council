#!/usr/bin/env python3
"""Validate the embedded KB validation plan and package command contract."""

from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

from _kb import is_portable_core, print_result, read_text, resolve_kb_root, resolve_skill_root


CORE_MODULES = {
    "validate_resource_limits",
    "validate_refs",
    "validate_routing",
    "validate_enforcement_outcomes",
    "validate_report",
    "validate_output_safety",
    "validate_policy_fixtures",
    "validate_validation_contract",
    "validate_adversarial",
    "run_adversarial_replay",
}
RELEASE_EXTRA_MODULES = {
    "validate_case_cards",
    "validate_gold",
    "validate_benchmarks",
    "validate_scope_gate",
    "verify_checksums",
}
PACKAGE_SCRIPT_TARGETS = {
    "inventory": ("inventory_kb", "--kb ."),
    "readiness:benchmarks": ("validate_benchmarks", "--kb . --min-count 15"),
    "validate:adversarial": ("validate_adversarial_suite", "--kb ."),
    "validate:benchmarks": ("validate_benchmarks", "--kb ."),
    "validate:cases": ("validate_case_cards", "--kb ."),
    "validate:checksums": ("verify_checksums", "--kb ."),
    "validate:contract": ("validate_validation_contract", "--kb ."),
    "validate:core": ("validate_core", "--kb ."),
    "validate:gold": ("validate_gold", "--kb ."),
    "validate:limits": ("validate_resource_limits", "--kb ."),
    "validate:live": ("validate_live_report", "--kb ."),
    "validate:outcomes": ("validate_enforcement_outcomes", "--kb ."),
    "validate:output": ("validate_output_safety", "--kb ."),
    "validate:policy": ("validate_policy_fixtures", "--kb ."),
    "validate:refs": ("validate_refs", "--kb ."),
    "validate:replay": ("run_adversarial_replay", "--kb ."),
    "validate:reports": ("validate_reports_and_output", "--kb ."),
    "validate:routing": ("validate_routing", "--kb ."),
    "validate:scope": ("validate_scope_gate", "--kb ."),
    "validate": ("validate_release", "--kb ."),
}


def load_json(path: Path, label: str, issues: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(f"cannot load {label}: {exc}")
        return {}
    if not isinstance(value, dict):
        issues.append(f"{label} must contain a JSON object")
        return {}
    return value


def expected_package_scripts(prefix: str) -> dict[str, str]:
    return {
        name: f"python -B {prefix}scripts/{module}.py {arguments}"
        for name, (module, arguments) in PACKAGE_SCRIPT_TARGETS.items()
    }


def local_script_graph(scripts_root: Path, issues: list[str]) -> dict[str, set[str]]:
    paths = {path.stem: path for path in scripts_root.glob("*.py")}
    graph: dict[str, set[str]] = {module: set() for module in paths}
    for module, path in paths.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            issues.append(f"cannot inspect script dependency graph for {path.name}: {exc}")
            continue
        for node in ast.walk(tree):
            imported: list[str] = []
            if isinstance(node, ast.Import):
                imported = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported = [node.module.split(".", 1)[0]]
            graph[module].update(name for name in imported if name in paths)
    return graph


def unreachable_scripts(
    graph: dict[str, set[str]], entry_modules: set[str]
) -> set[str]:
    reachable = set(entry_modules)
    pending = list(entry_modules)
    while pending:
        module = pending.pop()
        for dependency in graph.get(module, set()):
            if dependency not in reachable:
                reachable.add(dependency)
                pending.append(dependency)
    return set(graph) - reachable


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kb", default=None)
    args = parser.parse_args()
    root = resolve_kb_root(args.kb)
    portable_core = is_portable_core(root)
    skill_root = resolve_skill_root(root)
    issues: list[str] = []
    warnings: list[str] = []

    if not portable_core and skill_root != root / "skills" / "applaw":
        issues.append("maintenance KB must resolve skills/applaw as its active skill root")

    plan = load_json(skill_root / "scripts" / "validation_plan.json", "validation_plan.json", issues)
    if plan.get("schema_version") != "1.0":
        issues.append("validation_plan.json schema_version must be 1.0")

    core = plan.get("core_checks", [])
    release = plan.get("release_checks", [])
    if not isinstance(core, list) or not isinstance(release, list):
        issues.append("validation plans must be arrays")
        core, release = [], []
    for plan_name, entries in (("core_checks", core), ("release_checks", release)):
        for position, entry in enumerate(entries):
            label = f"validation_plan.json {plan_name}[{position}]"
            if not isinstance(entry, dict):
                issues.append(f"{label} must be an object")
                continue
            if set(entry) != {"name", "module", "args"}:
                issues.append(f"{label} must contain exactly name, module, and args")
            if not str(entry.get("name", "")).strip():
                issues.append(f"{label} has no display name")
            if not re.fullmatch(r"[a-z][a-z0-9_]*", str(entry.get("module", ""))):
                issues.append(f"{label} has an invalid module name")
            entry_args = entry.get("args")
            if not isinstance(entry_args, list) or not all(
                isinstance(value, str) for value in entry_args
            ):
                issues.append(f"{label} args must be an array of strings")
    core_modules = [str(entry.get("module", "")) for entry in core if isinstance(entry, dict)]
    release_modules = [str(entry.get("module", "")) for entry in release if isinstance(entry, dict)]
    if int(plan.get("core_max_checks", 0)) > 10 or len(core) > 10:
        issues.append("core validation plan must contain no more than ten checks")
    if len(core_modules) != len(set(core_modules)) or set(core_modules) != CORE_MODULES:
        issues.append(f"core validation modules must be exactly: {', '.join(sorted(CORE_MODULES))}")
    expected_release = CORE_MODULES | RELEASE_EXTRA_MODULES
    if len(release_modules) != len(set(release_modules)) or set(release_modules) != expected_release:
        issues.append(f"release validation modules must be exactly: {', '.join(sorted(expected_release))}")
    if not release_modules or release_modules[-1] != "verify_checksums":
        issues.append("checksum verification must be the final release check")

    gold_entries = [
        entry for entry in release
        if isinstance(entry, dict) and entry.get("module") == "validate_gold"
    ]
    if len(gold_entries) != 1 or "--strict-review" not in gold_entries[0].get("args", []):
        issues.append("release validation must run gold validation with --strict-review")

    ref_entries = [
        entry for entry in release
        if isinstance(entry, dict) and entry.get("module") == "validate_refs"
    ]
    if len(ref_entries) != 1:
        issues.append("release validation must contain exactly one reference check")
    elif portable_core and "--require-pdf-free" not in ref_entries[0].get("args", []):
        issues.append("portable-core release validation must require the PDF-free gate")
    elif not portable_core and "--require-pdf-free" in ref_entries[0].get("args", []):
        issues.append("maintenance release validation must preserve and validate maintenance PDFs")

    for module in sorted(set(core_modules + release_modules)):
        if not (skill_root / "scripts" / f"{module}.py").is_file():
            issues.append(f"validation plan references missing module: {module}.py")

    package = load_json(root / "package.json", "package.json", issues)
    package_version = str(package.get("version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+", package_version):
        issues.append("package.json version must be semantic x.y.z")
    if plan.get("release_version") != package_version:
        issues.append("validation_plan.json release_version must match package.json")

    versioned_documents = [
        (root / "constitutions" / "RESOURCE_LIMITS.json", "RESOURCE_LIMITS.json"),
        (root / "sources" / "source_capsules.json", "source_capsules.json"),
    ]
    case_index: dict = {}
    if portable_core:
        versioned_documents.extend(
            [
                (root / "RELEASE_PROFILE.json", "RELEASE_PROFILE.json"),
                (root / "cases" / "index.json", "cases/index.json"),
                (root / "eval" / "gold.json", "eval/gold.json"),
            ]
        )
    for path, label in versioned_documents:
        document = load_json(path, label, issues)
        if document.get("release_version") != package_version:
            issues.append(f"{label} release_version must match package.json")
        if label == "cases/index.json":
            case_index = document
    for entry in case_index.get("cases", []) if isinstance(case_index.get("cases"), list) else []:
        if not isinstance(entry, dict):
            continue
        bundle_path = str(entry.get("bundle_path", ""))
        bundle_file = (root / bundle_path).resolve()
        try:
            bundle_file.relative_to(root.resolve())
        except ValueError:
            issues.append(f"cases/index.json bundle path escapes the package root: {bundle_path}")
            continue
        bundle = load_json(bundle_file, bundle_path or "case bundle", issues)
        if bundle.get("release_version") != package_version:
            issues.append(f"{bundle_path} release_version must match package.json")

    scripts = package.get("scripts", {})
    if not isinstance(scripts, dict):
        issues.append("package.json scripts must be an object")
        scripts = {}
    prefix = "" if portable_core else "skills/applaw/"
    expected = expected_package_scripts(prefix)
    missing_scripts = set(expected) - set(scripts)
    unexpected_scripts = set(scripts) - set(expected)
    if missing_scripts:
        issues.append(f"package.json is missing scripts: {', '.join(sorted(missing_scripts))}")
    if unexpected_scripts:
        issues.append(f"package.json has unclassified scripts: {', '.join(sorted(unexpected_scripts))}")
    for name, command in expected.items():
        if scripts.get(name) != command:
            issues.append(f"package.json {name} must invoke {command!r}")

    entry_modules = {
        module for module, _arguments in PACKAGE_SCRIPT_TARGETS.values()
    } | set(core_modules) | set(release_modules)
    for module in sorted(entry_modules):
        if not (skill_root / "scripts" / f"{module}.py").is_file():
            issues.append(f"package entry point references missing module: {module}.py")
    script_graph = local_script_graph(skill_root / "scripts", issues)
    orphaned_scripts = unreachable_scripts(script_graph, entry_modules)
    if orphaned_scripts:
        issues.append(
            "scripts directory contains unreachable modules: "
            + ", ".join(f"{module}.py" for module in sorted(orphaned_scripts))
        )

    session_path = root / "constitutions" / "SESSION_LIMITS.md"
    if not session_path.is_file():
        issues.append("missing constitutions/SESSION_LIMITS.md")
    else:
        session_text = read_text(session_path)
        for phrase in ("npm run validate:core", "npm run validate", "complete composite release validation"):
            if phrase not in session_text:
                issues.append(f"SESSION_LIMITS.md missing validation phrase: {phrase}")

    skill_path = skill_root / "SKILL.md"
    if not skill_path.is_file():
        issues.append("missing active SKILL.md")
    else:
        skill_text = read_text(skill_path)
        for phrase in ("validate_live_report.py", "return the passing text unchanged", "npm run validate:core"):
            if phrase not in skill_text:
                issues.append(f"SKILL.md missing runtime-validation phrase: {phrase}")

    contract_path = skill_root / "references" / "report-contract.md"
    if not contract_path.is_file() or "# Public Report Contract v3" not in read_text(contract_path):
        issues.append("the active public report contract must be Report Contract v3")

    try:
        import validate_live_report

        if validate_live_report.input_mode_error(None, False) is None:
            issues.append("live validation without a path or --stdin must fail")
        sample = root / "eval" / "report_samples" / "2026-07-11-clean-subscription-standard.md"
        sample_text = sample.read_text(encoding="utf-8-sig")
        live_issues, _ = validate_live_report.validate_live_text(sample_text, root)
        if live_issues:
            issues.append("the complete low-risk v3 sample must pass the integrated live gate")
        unsafe_text = sample_text.replace(
            "Verdict: ",
            "Verdict: https://unsafe.example must not be exposed. ",
            1,
        )
        unsafe_issues, _ = validate_live_report.validate_live_text(unsafe_text, root)
        if not any("output safety" in issue for issue in unsafe_issues):
            issues.append("live validation must scan the same exact text for output safety")
    except Exception as exc:
        issues.append(f"integrated live-validator regression failed: {type(exc).__name__}: {exc}")

    warnings.append(
        f"validation contract: {len(core)} core checks; {len(release)} release checks; "
        f"profile={'portable-core' if portable_core else 'maintenance'}; "
        f"script graph={len(script_graph)} modules"
    )
    return print_result("Validation-contract consistency", issues, warnings)


if __name__ == "__main__":
    raise SystemExit(main())
