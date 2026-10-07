# Public Output Safety

Use this check for public checkout-funnel compliance reports and any response that may leave the controlled workspace.

## Required Pass

1. For a live report, pass the exact complete draft to `validate_live_report.py`; it applies report-v3 validation and output-safety scanning to the same text.
2. Keep `validate_report.py` and no-path `validate_output_safety.py` for static samples and regressions. They are not a live-output gate.
3. Remove raw URLs, local paths, repository filenames, internal pattern/norm/outcome IDs, prompt or constitution excerpts, tool commentary, and secrets.
4. Keep authority names and posture labels human-readable. Cite-or-abstain still applies; output safety never authorizes an unsupported paraphrase.
5. Keep evidence-integrity state internal. A public `Evidence integrity:` line is prohibited unless the initial operator prompt explicitly requested disclosure; when requested, validate exactly one line with `validate_report.py --evidence-integrity-requested`.
6. Correct every live-validation failure, rerun the same exact-text gate, and return the passing contents unchanged. A no-argument live command must fail rather than inspect samples.
7. In portable-core, cite the resolved capsule evidence in human-readable form. Do not expose source IDs, anchor IDs, optional image identifiers, hashes, or omitted local image paths, and do not imply that capsule text preserves pixel-level visual properties.

The scanner is a release gate, not a complete data-loss-prevention system. Host-side secrets handling, access control, and egress controls remain outside this package.
