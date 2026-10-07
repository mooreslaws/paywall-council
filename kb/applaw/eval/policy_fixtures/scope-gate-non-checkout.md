---
id: scope-gate-non-checkout
category: scope_gate
expected_handling: short_circuit_non_checkout
expected_risk_effect: low_by_default
expected_report_location: missing_context
prohibited_behavior: run_full_pattern_pipeline_on_non_checkout
---

# Evidence

The screenshot is a marketing or informational page: a hero headline, a feature grid, a "trusted by" logo strip, blog or article cards, or an FAQ, with no visible price, payment control, plan selector, or negative-option consent step anywhere on the page.

# Expected Behavior

Classify as `non_checkout` at A0 and skip A2-A6. Emit the short report shape: `RISK: very low`, `Material Findings: None.`, `Liability and Consequences: None.`, and a `Missing Context` bullet asking for the actual checkout or pricing screen plus the target jurisdiction. Never print the private numeric score.
