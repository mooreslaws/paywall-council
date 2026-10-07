# Clean Benchmarks

This folder is for lawful or low-risk checkout examples used to reduce false positives.

Do not add invented examples. Each benchmark should be tied to visible evidence, a local asset or documented source, and a specific reason the flow should not be flagged.

Current status: scaffold only. The v0.1 target is 15 real clean benchmark cards.

Use `_template.md` for new cards and run:

```bash
python -B skills/checkout-funnel-compliance/scripts/validate_benchmarks.py --kb .
```

For v0.1 readiness:

```bash
python -B skills/checkout-funnel-compliance/scripts/validate_benchmarks.py --kb . --min-count 15
```
