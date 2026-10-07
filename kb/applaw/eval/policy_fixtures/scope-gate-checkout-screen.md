---
id: scope-gate-checkout-screen
category: scope_gate
expected_handling: run_full_pipeline
expected_risk_effect: rubric_driven
expected_report_location: material_findings
prohibited_behavior: short_circuit_a_real_checkout_screen
---

# Evidence

The screenshot shows a specific price tied to a plan or item, a payment control such as a pay-now button or a card-entry field, or a negative-option consent step such as a subscription checkbox or plan toggle, at or near the call to action.

# Expected Behavior

Classify as `checkout_or_pricing` at A0 and continue the ordinary A1-A8 flow: run the five pattern specialists, route jurisdiction, and cite from `taxonomy/norms.yml`. Do not short-circuit a real checkout or pricing screen to the `non_checkout` report shape.
