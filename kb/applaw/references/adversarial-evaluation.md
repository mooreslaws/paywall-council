# Adversarial Evaluation

`eval/adversarial/` is a manual-replay robustness suite. It tests whether an agent preserves the canonical constitution, cite-or-abstain discipline, report contract, and session limits when prompts or evaluated evidence try to alter them.

This suite is distinct from `eval/gold/`: gold cards test checkout-pattern accuracy; adversarial cards test instruction integrity and resource-exhaustion resistance.

## How To Run

1. Load the canonical `constitutions/GLOBAL.md` and `constitutions/SESSION_LIMITS.md`.
2. Replay one card's `PROMPT / INJECTED EVIDENCE` in the channel described by the card.
3. Grade the response against that card's `PASS CRITERIA` and `FAILURE MODE`.
4. Do not reproduce a long injected payload in the resulting report.
5. Run `validate_adversarial.py` to check fixture structure and coverage; it does not claim to grade model behavior automatically.

All 27 accepted cards are regression specifications, not legal evidence or merchant findings.

## Deterministic Transcript Grading

`eval/adversarial_replays/` links six high-value cards to required and forbidden transcript patterns. Run:

```powershell
python -B scripts/run_adversarial_replay.py --kb .
```

With no transcript directory, this self-tests every rule against a known-safe and known-unsafe pair. A host evaluation harness can save actual responses as `<case-id>.txt` and pass their directory with `--transcript-dir`.

This runner is a transcript grader, not a live model runner. It does not send prompts, load screenshots into a model, or prove behavior that was never captured in a transcript.

