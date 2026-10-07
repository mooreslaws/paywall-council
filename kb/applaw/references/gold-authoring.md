# Gold Authoring

Gold cards are eval answers for known screens. They are stricter than ordinary notes because they teach the harness what counts as a correct answer.

## Required Qualities

- Expected internal score band and derived public five-level risk label. Keep the numeric score private in public reports.
- Expected patterns and norms.
- Expected citations with source id, source anchor ids, page, and paragraph anchors where available.
- Acceptable variants that preserve the legal/evidence meaning.
- Rejection criteria for hallucinated sources, missing citations, unsupported patterns, or overstated posture.

Store `jurisdiction` as `US`, `UK`, or `EU`; use nullable `sub_jurisdiction` with an ISO-style code for country-specific cards. Expected norms must include a supported material norm for that scope before any declared procedural companion. Reject procedural-only answers, direct pattern-to-procedure mapping, unstated-jurisdiction mapping, and country analogues.

Acceptable variants should preserve the evidence and legal meaning in plain language; legalistic wording is not a correctness requirement.

## Review Status

Use:

- `source_mapped` when source fields are checked.
- `converted_from_case_card` when derived from a case card but not separately reviewed.
- `needs_paragraph_anchor_review` when paragraph/source anchors still need verification.

Use `validate_gold.py --strict-review` when unresolved statuses should fail the run.

## Avoid Leakage

Gold cards should not reward memorized wording. They should specify evidence and anchors, while allowing equivalent explanations that cite the same local sources.

Legacy `source_file` values may remain when they resolve through `sources/source_capsules.json`. New gold records should prefer `source_id` and `source_anchor_ids`. Never require a PDF to ship with the evaluation package.

Portable-core gold copies require direct capsule fields and symmetric reverse references, but no `asset` frontmatter or bundled image. A historical visual anchor must provide a semantic summary or link through `linked_case_anchor_ids` to the corresponding case-card `EVIDENCE.` anchor. Missing optional visual evidence must not fail strict review when that capsule evidence resolves. A page, digest, URL, filename, or optional image identifier alone is not sufficient, and capsule text must not be treated as preserving pixel-level visual properties.
