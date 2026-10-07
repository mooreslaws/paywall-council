# Security Boundary

Version: 0.2.6  
Scope: portable checkout-funnel compliance package

## What This Package Enforces

The package provides instruction hierarchy and evidence-integrity rules, context-aware post-ingestion OCR/token/time admission, public-output scanning, package checksum verification, and a deterministic grader for saved adversarial transcripts. Its validators can reject non-conforming local artifacts when they are actually invoked.

## What The Host Or Webapp Must Enforce

The host or webapp owns attachment count, aggregate and per-file upload bytes, image dimensions and pixel count, PDF page count, archive expansion and decompression limits, MIME and file-signature validation, authentication, authorization, rate limits, quotas, storage isolation, secrets handling, tool permissions, network controls, and process sandboxing.

`constitutions/RESOURCE_LIMITS.json` starts after host ingestion. It is not an upload validator and does not make the portable package a hardened runtime.

## Integration Contract

1. The host validates and safely exposes accepted evidence.
2. Before one item or a complete screenshot batch begins, an integrated orchestration layer supplies `preflight_inputs.py` with the deployed context-window tokens; exact occupied-input tokens and their host/system, project, task, and existing-conversation components; cached input as a non-deductible subset; separately counted retrieved KB tokens; tool-output, response, and safety reserves; exact candidate evidence tokens; OCR characters; and elapsed-processing time. Standalone Claude or Codex sessions may omit this host-only step when those counters are unavailable; they must not fabricate them.
3. The orchestration layer rejects missing, negative, non-finite, inconsistent, double-counted, or over-window accounting. It never subtracts cached tokens from occupancy, guesses the context window, or silently truncates evidence.
4. The agent follows the constitutions and report contract.
5. Public Report Contract v3 text is checked by `validate_output_safety.py` and `validate_report.py` before delivery. The report validator rejects public numeric scores and rejects `Evidence integrity:` by default, accepting exactly one line only with `--evidence-integrity-requested` after an explicit initial-prompt request.
6. A release is accepted only after the composite `npm run validate` gate verifies `SHA256SUMS.txt` from the package root.
7. Live model replay belongs to the host or evaluation harness. `run_adversarial_replay.py` grades saved transcripts; it does not invoke a model.

If the host omits one of these calls, the corresponding package rule remains advisory rather than runtime-enforced.
