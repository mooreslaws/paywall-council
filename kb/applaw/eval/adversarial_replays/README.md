# Adversarial Transcript Replays

This directory links a selected set of accepted adversarial cards to deterministic transcript rules. `run_adversarial_replay.py` self-tests each rule with a known-safe and known-unsafe transcript, or grades host-produced text files named `<case-id>.txt`.

The runner does not invoke a model. A host evaluation harness must create the transcript from the source prompt and evidence before this package can grade it.

The injection replay requires internal recording while forbidding a default public `Evidence integrity:` line. Explicitly requested disclosure is tested separately by the report-validator fixtures.
