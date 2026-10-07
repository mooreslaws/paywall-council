#!/usr/bin/env python3
"""Small stdlib helpers for the checkout-funnel compliance KB."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


FAMILIES = {"disclosure", "consent", "pressure", "upsell", "cancellation"}
STAGES = {"lure", "commit", "hide", "charge", "block"}
SEVERITIES = {"low", "medium", "high"}
JURISDICTIONS = {"US", "EU", "UK"}
EU_SUB_JURISDICTION_ALIASES = {
    "fr": "FR",
    "france": "FR",
    "nl": "NL",
    "netherlands": "NL",
}
SUPPORTED_EU_SUB_JURISDICTIONS = frozenset(EU_SUB_JURISDICTION_ALIASES.values())
NORM_TYPES = {"material", "procedural"}
AVAILABILITY = {"full", "press_release_only", "partial", "unknown"}
RISK_BANDS = {"green", "yellow", "red"}
SCORE_BANDS = {"1-30", "31-60", "61-100"}
RELEASE_PROFILE_FILENAME = "RELEASE_PROFILE.json"
COMPACT_ARTIFACT_STORAGE = "compact-json-v1"


@dataclass(frozen=True)
class ArtifactRecord:
    """Logical KB artifact independent of its physical storage container."""

    kind: str
    logical_path: str
    container_path: str
    frontmatter: dict[str, Any]
    body: str


def _normalized_body(body: object) -> str:
    return str(body or "").replace("\r\n", "\n").replace("\r", "\n")


def artifact_semantic_payload(record: ArtifactRecord) -> dict[str, Any]:
    """Return the normalized representation covered by semantic parity checks."""
    return {
        "kind": record.kind,
        "logical_path": record.logical_path.replace("\\", "/"),
        "frontmatter": record.frontmatter,
        "body": _normalized_body(record.body),
    }


def artifact_semantic_digest(record: ArtifactRecord) -> str:
    payload = json.dumps(
        artifact_semantic_payload(record),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def artifact_semantic_aggregate(records: Iterable[ArtifactRecord]) -> str:
    """Hash a logical artifact set independently of its physical storage layout."""
    lines = [
        f"{record.logical_path}\t{artifact_semantic_digest(record)}"
        for record in sorted(records, key=lambda item: item.logical_path)
    ]
    return hashlib.sha256(("\n".join(lines) + "\n").encode("utf-8")).hexdigest()


def artifact_semantic_map_digest(records: Iterable[ArtifactRecord]) -> str:
    """Hash the logical-path-to-record-digest map used by compact case bundles."""
    record_digests = {
        record.logical_path: artifact_semantic_digest(record) for record in records
    }
    payload = json.dumps(
        record_digests,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def artifact_record_from_json(
    payload: object,
    *,
    expected_container_path: str,
) -> ArtifactRecord:
    if not isinstance(payload, dict):
        raise ValueError(f"{expected_container_path} contains a non-object artifact record")
    kind = str(payload.get("kind", "")).strip()
    logical_path = str(payload.get("logical_path", "")).strip().replace("\\", "/")
    container_path = str(payload.get("container_path", "")).strip().replace("\\", "/")
    frontmatter = payload.get("frontmatter")
    body = payload.get("body")
    if not kind or not logical_path or not container_path:
        raise ValueError(f"{expected_container_path} contains an incomplete artifact record")
    if container_path != expected_container_path:
        raise ValueError(
            f"{logical_path} declares container_path {container_path!r}, expected {expected_container_path!r}"
        )
    if not isinstance(frontmatter, dict) or not isinstance(body, str):
        raise ValueError(f"{logical_path} must contain object frontmatter and string body")
    record = ArtifactRecord(kind, logical_path, container_path, frontmatter, _normalized_body(body))
    expected_digest = str(payload.get("semantic_sha256", "")).strip()
    actual_digest = artifact_semantic_digest(record)
    if not re.fullmatch(r"[0-9a-f]{64}", expected_digest) or expected_digest != actual_digest:
        raise ValueError(f"{logical_path} has an invalid semantic_sha256")
    return record


def resolve_kb_root(kb: str | None = None) -> Path:
    start = Path(kb).resolve() if kb else Path.cwd().resolve()
    if start.is_file():
        start = start.parent
    # An explicit --kb value is a trust boundary. Never walk out of that root
    # and silently select a parent workspace when a standalone copy is broken.
    if kb is not None:
        return start
    for candidate in [start, *start.parents]:
        if (candidate / "taxonomy").is_dir() and (candidate / "cases").is_dir():
            return candidate
    if kb is None:
        binding = Path(__file__).resolve().parent.parent / "references" / "installed-kb-root.txt"
        if binding.is_file():
            raw = binding.read_text(encoding="utf-8-sig").strip()
            if raw:
                bound = Path(raw).expanduser().resolve()
                if (bound / "taxonomy").is_dir() and (bound / "cases").is_dir():
                    return bound
    return start


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def split_inline_list(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    out: list[str] = []
    buf: list[str] = []
    quote: str | None = None
    for char in raw:
        if quote:
            if char == quote:
                quote = None
            else:
                buf.append(char)
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == ",":
            item = "".join(buf).strip()
            if item:
                out.append(strip_quotes(item))
            buf = []
            continue
        buf.append(char)
    item = "".join(buf).strip()
    if item:
        out.append(strip_quotes(item))
    return out


def parse_value(raw: str) -> Any:
    raw = raw.strip()
    if raw == "":
        return ""
    if raw in {"null", "~"}:
        return None
    if raw.startswith("[") and raw.endswith("]"):
        return split_inline_list(raw)
    return strip_quotes(raw)


def normalize_sub_jurisdiction(value: object) -> str | None:
    """Normalize a supported EU country token to its ISO-style code."""
    if value is None:
        return None
    token = " ".join(str(value).strip().split())
    if not token or token.casefold() in {"null", "none", "~"}:
        return None
    normalized = EU_SUB_JURISDICTION_ALIASES.get(token.casefold())
    if normalized:
        return normalized
    raise ValueError(f"unsupported EU sub-jurisdiction: {value}")


def normalize_jurisdiction_scope(
    jurisdiction: object,
    sub_jurisdiction: object = None,
) -> tuple[str, str | None]:
    """Normalize an external jurisdiction alias to the canonical two-field scope."""
    raw = str(jurisdiction).strip()
    if not raw:
        raise ValueError("jurisdiction cannot be empty")

    inline_sub: str | None = None
    if ":" in raw:
        base, inline_sub = raw.split(":", 1)
    elif raw.upper().startswith("EU-"):
        base, inline_sub = "EU", raw[3:]
    else:
        base = raw

    base = base.strip().upper()
    if base not in JURISDICTIONS:
        raise ValueError(f"unsupported jurisdiction: {jurisdiction}")
    if inline_sub is not None and sub_jurisdiction not in (None, "", "null", "~"):
        raise ValueError("sub-jurisdiction was supplied twice")

    raw_sub = inline_sub if inline_sub is not None else sub_jurisdiction
    normalized_sub = normalize_sub_jurisdiction(raw_sub)
    if normalized_sub is not None and base != "EU":
        raise ValueError(f"{base} does not accept an EU sub-jurisdiction")
    return base, normalized_sub


def canonical_scope(scope: tuple[str, str | None]) -> dict[str, str | None]:
    """Return the single canonical internal jurisdiction representation."""
    return {"jurisdiction": scope[0], "sub_jurisdiction": scope[1]}


def scope_label(scope: tuple[str, str | None]) -> str:
    """Return a compact human-readable label without changing internal storage."""
    base, sub = scope
    return f"{base}:{sub}" if sub else base


def scope_matches(
    candidate_jurisdiction: object,
    candidate_sub_jurisdiction: object,
    target: tuple[str, str | None],
) -> bool:
    """Match a regional record or an exact country record to an explicit target."""
    candidate = normalize_jurisdiction_scope(candidate_jurisdiction, candidate_sub_jurisdiction)
    target_base, target_sub = target
    candidate_base, candidate_sub = candidate
    if candidate_base != target_base:
        return False
    return candidate_sub is None or candidate_sub == target_sub


def parse_scalar(raw: str) -> Any:
    """Parse the small scalar subset used by the canonical YAML registries."""
    raw = raw.strip()
    if raw == "null":
        return None
    if raw in {"true", "false"}:
        return raw == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return parse_value(raw)


def ensure_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    if isinstance(value, str) and value.strip().startswith("["):
        return split_inline_list(value)
    return [str(value).strip()]


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    text = read_text(path)
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in lines[1:end]:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_key:
            current = data.setdefault(current_key, [])
            if isinstance(current, list):
                current.append(parse_value(stripped[2:]))
            continue
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        key = key.strip()
        value = parse_value(raw)
        data[key] = [] if value == "" else value
        current_key = key if value == "" else None
    body = "\n".join(lines[end + 1 :]).strip()
    return data, body


def parse_yaml_items(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    current_key: str | None = None
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("- "):
            if current is not None:
                items.append(current)
            current = {}
            current_key = None
            entry = stripped[2:]
            if ":" in entry:
                key, raw = entry.split(":", 1)
                current[key.strip()] = parse_value(raw)
            continue
        if current is None:
            continue
        if stripped.startswith("- ") and current_key:
            current.setdefault(current_key, []).append(parse_value(stripped[2:]))
            continue
        if ":" in line:
            key, raw = line.split(":", 1)
            key = key.strip()
            value = parse_value(raw)
            current[key] = [] if value == "" else value
            current_key = key if value == "" else None
    if current is not None:
        items.append(current)
    return items


def parse_outcome_registry(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse taxonomy/enforcement_outcomes.yml without a PyYAML dependency."""
    if not path.exists():
        return {}, []
    metadata: dict[str, Any] = {}
    outcomes: list[dict[str, Any]] = []
    current_metadata_list: str | None = None
    current: dict[str, Any] | None = None
    nested_key: str | None = None
    in_outcomes = False

    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line == "outcomes:":
            in_outcomes = True
            current_metadata_list = None
            continue

        if not in_outcomes:
            if line.startswith("  - ") and current_metadata_list:
                metadata.setdefault(current_metadata_list, []).append(parse_scalar(stripped[2:]))
                continue
            if not line.startswith(" ") and ":" in line:
                key, raw = line.split(":", 1)
                value = parse_scalar(raw)
                metadata[key.strip()] = [] if value == "" else value
                current_metadata_list = key.strip() if value == "" else None
            continue

        if line.startswith("  - "):
            if current is not None:
                outcomes.append(current)
            current = {}
            nested_key = None
            entry = stripped[2:]
            if ":" in entry:
                key, raw = entry.split(":", 1)
                current[key.strip()] = parse_scalar(raw)
            continue
        if current is None:
            continue
        if line.startswith("      ") and nested_key and ":" in stripped:
            key, raw = stripped.split(":", 1)
            nested = current.setdefault(nested_key, {})
            if isinstance(nested, dict):
                nested[key.strip()] = parse_scalar(raw)
            continue
        if line.startswith("    ") and ":" in stripped:
            key, raw = stripped.split(":", 1)
            value = parse_scalar(raw)
            if value == "":
                current[key.strip()] = {}
                nested_key = key.strip()
            else:
                current[key.strip()] = value
                nested_key = None
    if current is not None:
        outcomes.append(current)
    return metadata, outcomes


def id_set(items: Iterable[dict[str, Any]]) -> set[str]:
    return {str(item.get("id", "")).strip() for item in items if str(item.get("id", "")).strip()}


def duplicate_ids(items: Iterable[dict[str, Any]]) -> list[str]:
    seen: set[str] = set()
    dupes: set[str] = set()
    for item in items:
        item_id = str(item.get("id", "")).strip()
        if not item_id:
            continue
        if item_id in seen:
            dupes.add(item_id)
        seen.add(item_id)
    return sorted(dupes)


def case_dirs(root: Path) -> list[Path]:
    cases_root = root / "cases"
    if not cases_root.exists():
        return []
    return sorted([p for p in cases_root.iterdir() if p.is_dir()])


def case_card_paths(root: Path) -> list[Path]:
    paths: list[Path] = []
    for folder in case_dirs(root):
        paths.extend(
            sorted(p for p in folder.glob("*.md") if p.name != "_case.md" and not p.name.startswith("_"))
        )
    return paths


def gold_paths(root: Path) -> list[Path]:
    gold_root = root / "eval" / "gold"
    if not gold_root.exists():
        return []
    return sorted(gold_root.glob("*.md"))


def benchmark_paths(root: Path) -> list[Path]:
    clean_root = root / "benchmarks" / "clean"
    if not clean_root.exists():
        return []
    return sorted(
        p
        for p in clean_root.glob("*.md")
        if p.name.lower() != "readme.md" and not p.name.startswith("_")
    )


def _markdown_artifact(path: Path, root: Path, kind: str) -> ArtifactRecord:
    frontmatter, body = parse_frontmatter(path)
    logical_path = relative(path, root)
    return ArtifactRecord(kind, logical_path, logical_path, frontmatter, body)


def _compact_case_records(root: Path) -> list[ArtifactRecord]:
    index_path = root / "cases" / "index.json"
    if not index_path.is_file():
        return []
    index = load_json(index_path)
    if (
        not isinstance(index, dict)
        or index.get("schema_version") != "1.0"
        or index.get("artifact_storage") != COMPACT_ARTIFACT_STORAGE
    ):
        raise ValueError("cases/index.json is not a compact-json-v1 case index")
    release_version = str(index.get("release_version", "")).strip()
    if not release_version:
        raise ValueError("cases/index.json has no release_version")
    entries = index.get("cases")
    if not isinstance(entries, list):
        raise ValueError("cases/index.json cases must be a list")
    records: list[ArtifactRecord] = []
    seen_bundles: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("cases/index.json contains a non-object case entry")
        bundle_path = str(entry.get("bundle_path", "")).strip().replace("\\", "/")
        if (
            not bundle_path.startswith("cases/")
            or not bundle_path.endswith(".json")
            or bundle_path == "cases/index.json"
        ):
            raise ValueError(f"cases/index.json has an invalid bundle path: {bundle_path!r}")
        if bundle_path.casefold() in seen_bundles:
            raise ValueError(f"cases/index.json repeats bundle path: {bundle_path}")
        seen_bundles.add(bundle_path.casefold())
        bundle_file = root / Path(*PurePosixPath(bundle_path).parts)
        bundle = load_json(bundle_file)
        if (
            not isinstance(bundle, dict)
            or bundle.get("schema_version") != "1.0"
            or bundle.get("artifact_storage") != COMPACT_ARTIFACT_STORAGE
            or bundle.get("bundle_path") != bundle_path
            or bundle.get("release_version") != release_version
        ):
            raise ValueError(f"{bundle_path} is not a valid compact case bundle")
        payloads = bundle.get("records")
        if not isinstance(payloads, list):
            raise ValueError(f"{bundle_path} records must be a list")
        bundle_records = [
            artifact_record_from_json(payload, expected_container_path=bundle_path)
            for payload in payloads
        ]
        indexed_paths = entry.get("logical_paths")
        actual_paths = [record.logical_path for record in bundle_records]
        if not isinstance(indexed_paths, list) or indexed_paths != actual_paths:
            raise ValueError(f"{bundle_path} logical paths do not match cases/index.json")

        headers = [record for record in bundle_records if record.kind == "case_header"]
        coverages = [record for record in bundle_records if record.kind == "case_coverage"]
        cards = [record for record in bundle_records if record.kind == "case"]
        anchor_refs = [
            anchor_id
            for record in bundle_records
            for anchor_id in ensure_list(record.frontmatter.get("source_anchor_ids"))
        ]
        case_id = str(bundle.get("case_id", "")).strip()
        expected_summary = {
            "anchor_count": len(set(anchor_refs)),
            "anchor_reference_count": len(anchor_refs),
            "case_cards": len(cards),
            "case_headers": len(headers),
            "coverage_records": len(coverages),
            "semantic_records": len(bundle_records),
            "semantic_sha256": artifact_semantic_map_digest(bundle_records),
        }
        if bundle.get("summary") != expected_summary:
            raise ValueError(f"{bundle_path} summary does not match its logical records")
        expected_entry = {
            "anchor_count": expected_summary["anchor_count"],
            "anchor_reference_count": expected_summary["anchor_reference_count"],
            "bundle_path": bundle_path,
            "card_count": len(cards),
            "case_id": case_id,
            "coverage_logical_path": coverages[0].logical_path if len(coverages) == 1 else None,
            "figure_ids": [str(record.frontmatter.get("figure_id", "")) for record in cards],
            "header_logical_path": headers[0].logical_path if len(headers) == 1 else None,
            "logical_paths": actual_paths,
            "semantic_record_count": len(bundle_records),
        }
        if entry != expected_entry:
            raise ValueError(f"{bundle_path} metadata does not match cases/index.json")
        records.extend(bundle_records)

    expected_totals = {
        "anchor_count": sum(int(entry.get("anchor_count", 0)) for entry in entries),
        "anchor_reference_count": sum(
            int(entry.get("anchor_reference_count", 0)) for entry in entries
        ),
        "case_cards": sum(int(entry.get("card_count", 0)) for entry in entries),
        "case_headers": sum(1 for record in records if record.kind == "case_header"),
        "cases": len(entries),
        "coverage_records": sum(1 for record in records if record.kind == "case_coverage"),
        "semantic_records": len(records),
    }
    if index.get("totals") != expected_totals:
        raise ValueError("cases/index.json totals do not match its case bundles")
    return records


def _compact_gold_records(root: Path) -> list[ArtifactRecord]:
    registry_path = root / "eval" / "gold.json"
    if not registry_path.is_file():
        return []
    registry = load_json(registry_path)
    if (
        not isinstance(registry, dict)
        or registry.get("schema_version") != "1.0"
        or registry.get("artifact_storage") != COMPACT_ARTIFACT_STORAGE
        or not str(registry.get("release_version", "")).strip()
    ):
        raise ValueError("eval/gold.json is not a compact-json-v1 gold registry")
    payloads = registry.get("records")
    if not isinstance(payloads, list):
        raise ValueError("eval/gold.json records must be a list")
    records = [
        artifact_record_from_json(payload, expected_container_path="eval/gold.json")
        for payload in payloads
    ]
    logical_index = registry.get("logical_path_index")
    expected_index = {record.logical_path: position for position, record in enumerate(records)}
    if logical_index != expected_index:
        raise ValueError("eval/gold.json logical_path_index does not match its records")
    by_case: dict[str, int] = {}
    review_status_counts: dict[str, int] = {}
    for record in records:
        case_id = str(record.frontmatter.get("case_id", "")).strip()
        review_status = str(record.frontmatter.get("review_status", "")).strip()
        by_case[case_id] = by_case.get(case_id, 0) + 1
        review_status_counts[review_status] = review_status_counts.get(review_status, 0) + 1
    expected_summary = {
        "by_case": dict(sorted(by_case.items())),
        "card_count": len(records),
        "review_status_counts": dict(sorted(review_status_counts.items())),
        "semantic_sha256": artifact_semantic_aggregate(records),
    }
    if registry.get("summary") != expected_summary:
        raise ValueError("eval/gold.json summary does not match its logical records")
    return records


def case_header_records(root: Path) -> list[ArtifactRecord]:
    compact = [record for record in _compact_case_records(root) if record.kind == "case_header"]
    if compact or (root / "cases" / "index.json").is_file():
        return compact
    return [
        _markdown_artifact(folder / "_case.md", root, "case_header")
        for folder in case_dirs(root)
        if (folder / "_case.md").is_file()
    ]


def case_coverage_records(root: Path) -> list[ArtifactRecord]:
    compact = [record for record in _compact_case_records(root) if record.kind == "case_coverage"]
    if compact or (root / "cases" / "index.json").is_file():
        return compact
    records: list[ArtifactRecord] = []
    for folder in case_dirs(root):
        path = folder / "_coverage.json"
        if path.is_file():
            logical_path = relative(path, root)
            data = load_json(path)
            if not isinstance(data, dict):
                raise ValueError(f"{logical_path} must contain an object")
            records.append(ArtifactRecord("case_coverage", logical_path, logical_path, data, ""))
    return records


def case_card_records(root: Path) -> list[ArtifactRecord]:
    compact = [record for record in _compact_case_records(root) if record.kind == "case"]
    if compact or (root / "cases" / "index.json").is_file():
        return compact
    return [_markdown_artifact(path, root, "case") for path in case_card_paths(root)]


def gold_records(root: Path) -> list[ArtifactRecord]:
    compact = _compact_gold_records(root)
    if compact or (root / "eval" / "gold.json").is_file():
        return compact
    return [_markdown_artifact(path, root, "gold") for path in gold_paths(root)]


def benchmark_records(root: Path) -> list[ArtifactRecord]:
    return [_markdown_artifact(path, root, "benchmark") for path in benchmark_paths(root)]


def iter_artifact_records(
    root: Path,
    kinds: Iterable[str] | None = None,
) -> Iterable[ArtifactRecord]:
    selected = set(kinds) if kinds is not None else None
    groups = [
        *case_header_records(root),
        *case_coverage_records(root),
        *case_card_records(root),
        *gold_records(root),
        *benchmark_records(root),
    ]
    for record in groups:
        if selected is None or record.kind in selected:
            yield record


def artifact_record_index(root: Path) -> dict[str, list[ArtifactRecord]]:
    index: dict[str, list[ArtifactRecord]] = {}
    for record in iter_artifact_records(root):
        logical_path = record.logical_path.replace("\\", "/")
        index.setdefault(logical_path, []).append(record)
    return index


def artifact_records_for_path(root: Path, artifact: str | Path | ArtifactRecord) -> list[ArtifactRecord]:
    logical_path = normalize_artifact_path(
        root, artifact.logical_path if isinstance(artifact, ArtifactRecord) else artifact
    )
    return artifact_record_index(root).get(logical_path, [])


def artifact_resolution_count(root: Path, artifact: str | Path | ArtifactRecord) -> int:
    matches = artifact_records_for_path(root, artifact)
    if matches:
        return len(matches)
    logical_path = normalize_artifact_path(
        root, artifact.logical_path if isinstance(artifact, ArtifactRecord) else artifact
    )
    return int((root / Path(*PurePosixPath(logical_path).parts)).is_file())


def artifact_logical_exists(root: Path, artifact: str | Path | ArtifactRecord) -> bool:
    return artifact_resolution_count(root, artifact) == 1


def case_lookup(root: Path) -> dict[str, Path]:
    lookup: dict[str, Path] = {}
    for folder in case_dirs(root):
        keys = {folder.name, folder.name.replace("_", "-")}
        fm, _ = parse_frontmatter(folder / "_case.md") if (folder / "_case.md").exists() else ({}, "")
        case_id = str(fm.get("case_id", "")).strip()
        if case_id:
            keys.update({case_id, case_id.replace("-", "_")})
        for key in keys:
            lookup[key] = folder
    return lookup


def resolve_case_card(root: Path, ref: str) -> ArtifactRecord | None:
    """Resolve a case/figure reference to one logical case-card record."""
    ref = ref.strip().replace("\\", "/")
    if "/" not in ref:
        return None
    case_key, figure = ref.split("/", 1)
    figure_id = figure[:-3] if figure.endswith(".md") else figure
    for record in case_card_records(root):
        logical = PurePosixPath(record.logical_path)
        folder_key = logical.parent.name
        case_id = str(record.frontmatter.get("case_id", "")).strip()
        aliases = {
            folder_key,
            folder_key.replace("_", "-"),
            folder_key.replace("-", "_"),
            case_id,
            case_id.replace("_", "-"),
            case_id.replace("-", "_"),
        }
        if case_key in aliases and (
            logical.stem == figure_id
            or str(record.frontmatter.get("figure_id", "")).strip() == figure_id
        ):
            return record
    return None


def case_card_exists(root: Path, ref: str) -> bool:
    if resolve_case_card(root, ref) is not None:
        return True
    ref = ref.strip().replace("\\", "/")
    if "/" not in ref:
        return False
    case_key, figure = ref.split("/", 1)
    folder = case_lookup(root).get(case_key) or case_lookup(root).get(case_key.replace("-", "_"))
    if not folder:
        return False
    name = figure if figure.endswith(".md") else f"{figure}.md"
    return (folder / name).exists()


def repo_path_exists(root: Path, rel: str) -> bool:
    rel = strip_quotes(str(rel)).replace("\\", "/")
    if not rel:
        return False
    return (root / rel).exists() or artifact_logical_exists(root, rel)


def normalize_source_alias(value: object) -> str:
    return strip_quotes(str(value or "")).strip().replace("\\", "/").removeprefix("./").casefold()


@lru_cache(maxsize=8)
def _load_source_capsules_cached(path_text: str, modified_ns: int) -> dict[str, Any]:
    del modified_ns
    path = Path(path_text)
    if not path.is_file():
        return {}
    data = json.loads(read_text(path))
    return data if isinstance(data, dict) else {}


def load_source_capsules(root: Path) -> dict[str, Any]:
    path = root / "sources" / "source_capsules.json"
    if not path.is_file():
        return {}
    return _load_source_capsules_cached(str(path.resolve()), path.stat().st_mtime_ns)


@lru_cache(maxsize=8)
def _load_release_profile_cached(path_text: str, modified_ns: int) -> dict[str, Any]:
    del modified_ns
    path = Path(path_text)
    if not path.is_file():
        return {}
    data = json.loads(read_text(path))
    return data if isinstance(data, dict) else {}


def load_release_profile(root: Path) -> dict[str, Any]:
    """Load a portable release profile, or describe the active maintenance KB."""
    path = root / RELEASE_PROFILE_FILENAME
    if path.is_file():
        return _load_release_profile_cached(str(path.resolve()), path.stat().st_mtime_ns)
    return {
        "schema_version": "1.0",
        "profile": "maintenance",
        "bundled_visual_assets": (root / "assets").is_dir(),
        "evidence_mode": "assets-and-capsules",
        "optional_evidence_pack_required": False,
    }


def is_portable_core(root: Path) -> bool:
    return load_release_profile(root).get("profile") == "portable-core"


def source_capsule_id_index(root: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in load_source_capsules(root).get("sources", []):
        if not isinstance(record, dict):
            continue
        source_id = str(record.get("source_id", "")).strip()
        if source_id:
            index.setdefault(source_id, record)
    return index


def source_anchor_index(root: Path) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    index: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for record in load_source_capsules(root).get("sources", []):
        if not isinstance(record, dict):
            continue
        for anchor in record.get("anchors", []):
            if not isinstance(anchor, dict):
                continue
            anchor_id = str(anchor.get("anchor_id", "")).strip()
            if anchor_id:
                index.setdefault(anchor_id, (record, anchor))
    return index


def resolve_source_by_id(root: Path, source_id: object) -> dict[str, Any] | None:
    return source_capsule_id_index(root).get(str(source_id or "").strip())


def resolve_anchor_by_id(
    root: Path, anchor_id: object
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    return source_anchor_index(root).get(str(anchor_id or "").strip())


def normalize_artifact_path(root: Path, artifact: str | Path | ArtifactRecord) -> str:
    """Return a safe root-relative POSIX path without allowing root escape."""
    if isinstance(artifact, ArtifactRecord):
        artifact = artifact.logical_path
    raw = Path(artifact)
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        resolved = (root / raw).resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"artifact path escapes selected KB root: {artifact}") from exc


def artifact_reverse_resolution(
    root: Path, artifact: str | Path | ArtifactRecord
) -> dict[str, Any]:
    """Resolve an artifact only through capsule reverse references."""
    rel = normalize_artifact_path(root, artifact)
    source_ids: set[str] = set()
    anchors: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for record in load_source_capsules(root).get("sources", []):
        if not isinstance(record, dict):
            continue
        source_id = str(record.get("source_id", "")).strip()
        if rel in ensure_list(record.get("referenced_by")):
            source_ids.add(source_id)
        for anchor in record.get("anchors", []):
            if not isinstance(anchor, dict) or rel not in ensure_list(anchor.get("referenced_by")):
                continue
            anchor_id = str(anchor.get("anchor_id", "")).strip()
            if anchor_id:
                anchors[anchor_id] = (record, anchor)
                source_ids.add(source_id)
    return {
        "artifact_path": rel,
        "source_ids": sorted(source_ids),
        "source_anchor_ids": sorted(anchors),
        "anchor_records": anchors,
    }


def resolve_artifact_evidence(
    root: Path,
    artifact: str | Path | ArtifactRecord,
    frontmatter: dict[str, Any] | None = None,
    *,
    require_direct: bool = False,
) -> dict[str, Any]:
    """Resolve artifact provenance and return capsule evidence when visuals are absent."""
    reverse = artifact_reverse_resolution(root, artifact)
    fm = (
        artifact.frontmatter
        if isinstance(artifact, ArtifactRecord) and frontmatter is None
        else (frontmatter or {})
    )
    errors: list[str] = []
    direct_source_id = str(fm.get("source_id", "")).strip()
    direct_anchor_ids = ensure_list(fm.get("source_anchor_ids"))
    reverse_source_ids = set(reverse["source_ids"])
    reverse_anchor_ids = set(reverse["source_anchor_ids"])

    if require_direct and not direct_source_id:
        errors.append("portable-core artifact is missing direct source_id")
    if require_direct and not direct_anchor_ids:
        errors.append("portable-core artifact is missing direct source_anchor_ids")

    source_id = direct_source_id or (next(iter(reverse_source_ids)) if len(reverse_source_ids) == 1 else "")
    anchor_ids = direct_anchor_ids or sorted(reverse_anchor_ids)
    if not source_id:
        errors.append(f"reverse references resolve {len(reverse_source_ids)} source records")
    if not anchor_ids:
        errors.append("reverse references resolve no source anchors")
    if direct_source_id and reverse_source_ids != {direct_source_id}:
        errors.append(
            f"direct source_id {direct_source_id} is not symmetric with reverse sources {sorted(reverse_source_ids)}"
        )
    if direct_anchor_ids and reverse_anchor_ids != set(direct_anchor_ids):
        errors.append(
            "direct source_anchor_ids are not symmetric with reverse anchor references"
        )

    source = resolve_source_by_id(root, source_id) if source_id else None
    if source_id and source is None:
        errors.append(f"source_id does not resolve: {source_id}")
    anchors: list[dict[str, Any]] = []
    summaries: list[str] = []
    historical_visual = False
    visual_asset_available = False
    limitations: list[str] = []
    for anchor_id in anchor_ids:
        resolved = resolve_anchor_by_id(root, anchor_id)
        if not resolved:
            errors.append(f"source anchor does not resolve: {anchor_id}")
            continue
        anchor_source, anchor = resolved
        if source_id and anchor_source.get("source_id") != source_id:
            errors.append(f"anchor {anchor_id} belongs to a different source")
            continue
        anchors.append(anchor)
        summary = " ".join(str(anchor.get("evidence_summary", "")).split())
        if summary and summary not in summaries:
            summaries.append(summary)
        asset_refs = ensure_list(anchor.get("asset_refs"))
        is_visual = anchor.get("historical_visual_evidence") is True or bool(asset_refs)
        historical_visual = historical_visual or is_visual
        visual_asset_available = visual_asset_available or any((root / rel).is_file() for rel in asset_refs)
        for key in ("visual_evidence_limitations", "limitations"):
            value = " ".join(str(anchor.get(key, "")).split())
            if value and value not in limitations:
                limitations.append(value)
    if historical_visual and not summaries and not visual_asset_available:
        errors.append("historical visual evidence has no semantic evidence summary")

    return {
        "artifact_path": reverse["artifact_path"],
        "source_id": source_id or None,
        "source_anchor_ids": anchor_ids,
        "source": source,
        "anchors": anchors,
        "evidence_summaries": summaries,
        "historical_visual_evidence": historical_visual,
        "visual_asset_available": visual_asset_available,
        "evidence_mode": "visual-and-capsule" if visual_asset_available else "capsule",
        "limitations": limitations,
        "errors": errors,
    }


def source_capsule_index(root: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in load_source_capsules(root).get("sources", []):
        if not isinstance(record, dict):
            continue
        aliases = ensure_list(record.get("aliases"))
        original = record.get("original_document", {})
        if isinstance(original, dict) and original.get("filename"):
            aliases.append(str(original["filename"]))
        for alias in aliases:
            normalized = normalize_source_alias(alias)
            if not normalized:
                continue
            index.setdefault(normalized, record)
            index.setdefault(Path(normalized).name, record)
    return index


def resolve_source_capsule(root: Path, source_file: object) -> dict[str, Any] | None:
    normalized = normalize_source_alias(source_file)
    if not normalized:
        return None
    index = source_capsule_index(root)
    return index.get(normalized) or index.get(Path(normalized).name)


def source_file_exists(root: Path, source_file: str) -> bool:
    source_file = strip_quotes(str(source_file)).replace("\\", "/")
    if not source_file:
        return False
    candidates = [
        root / source_file,
        root / "case_law" / source_file,
        root / "downloaded_pdfs" / source_file,
    ]
    if any(path.exists() for path in candidates):
        return True
    capsule = resolve_source_capsule(root, source_file)
    if not capsule:
        return False
    original = capsule.get("original_document", {})
    digest = str(original.get("sha256", "")) if isinstance(original, dict) else ""
    return bool(
        re.fullmatch(r"[0-9a-f]{64}", digest)
        and str(capsule.get("source_id", "")).strip()
        and str(capsule.get("title", "")).strip()
        and capsule.get("referenced") is True
    )


def relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def resolve_skill_root(root: Path) -> Path:
    """Resolve either the maintenance nested skill or a flattened skill-root release."""
    if (
        (root / "SKILL.md").is_file()
        and (root / "scripts").is_dir()
        and (root / "references").is_dir()
    ):
        return root
    for skill_name in ("applaw", "checkout-funnel-compliance"):
        nested = root / "skills" / skill_name
        if (
            (nested / "SKILL.md").is_file()
            and (nested / "scripts").is_dir()
            and (nested / "references").is_dir()
        ):
            return nested
    return root / "skills" / "applaw"


def section_has_text(body: str, label: str) -> bool:
    pattern = re.compile(rf"{re.escape(label)}\.\s*\S", re.IGNORECASE)
    return bool(pattern.search(body))


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def print_result(title: str, issues: list[str], warnings: list[str] | None = None) -> int:
    warnings = warnings or []
    print(title)
    if issues:
        print(f"FAIL: {len(issues)} issue(s)")
        for issue in issues:
            print(f"- {issue}")
    else:
        print("PASS: no hard issues")
    if warnings:
        print(f"WARN: {len(warnings)} warning(s)")
        for warning in warnings:
            print(f"- {warning}")
    return 1 if issues else 0
