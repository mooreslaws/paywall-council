# Clean Benchmark Authoring

Clean benchmarks reduce false positives. They should be real or source-backed low-risk checkout examples, not invented "green" stories.

## What Counts

A clean benchmark should show:

- Material price and renewal terms before payment.
- Clear cancellation information where relevant.
- Active consent when an add-on, subscription, trial, or negative option exists.
- No preselected paid extras.
- No misleading urgency or scarcity.
- Low-risk explanation tied to visible evidence.

## Fields

Use `benchmarks/clean/_template.md` as the starting shape. Fill the evidence source and, for canonical maintenance, any available asset field. Every benchmark must resolve one source capsule and at least one local anchor; multi-page benchmarks may resolve several anchors. Never rely on a URL, filename, digest, page, or optional image identifier alone.

Portable-core copies carry direct `source_id` and `source_anchor_ids`, omit `asset` frontmatter, and remain valid without a shareable image. Record the absent-image limitation and use capsule evidence. Do not claim that extracted text or semantic summaries preserve color, contrast, relative prominence, spacing, or location.

## False-Positive Trap Coverage

Map the benchmark to traps it protects against, such as:

- `clear-renewal-disclosure-before-payment`
- `optional-unselected-addon`
- `same-channel-cancellation`
- `non-deceptive-progress-indicator`
- `genuine-limited-time-offer-with-support`

## Validation

Run:

`python -B scripts/validate_benchmarks.py --kb <kb-root>`

Use `--min-count 15` for readiness checks that require the complete clean-benchmark floor.

