---
id: clean-footer-day-price
category: known_clean
expected_handling: false_positive_trap
expected_risk_effect: low_by_default
expected_report_location: mitigating
prohibited_behavior: flag_without_material_defect
---

# Evidence

The checkout shows a daily equivalent, the full monthly charge and renewal cadence with equal prominence, and standard legal links in a smaller footer.

# Expected Behavior

Do not flag the daily price or footer by themselves. A finding requires a specific material disclosure, consent, price, or cancellation defect beyond these ordinary conventions.
